import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union, Callable
from inspectfuncs import inspect_data_distribution, inspect_data_structure
from modelfuncs import handle_surrogate_data, expected_improvement, latin_hypercube, parse_llm_response
from agglomfuncs import dpp_select
from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel, RBF, RationalQuadratic, WhiteKernel, DotProduct
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
import anthropic
from functools import lru_cache
import logging
import json
from pathlib import Path
import optuna
from scipy.stats import norm
from scipy.optimize import minimize
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizationStrategy:
    """Base class for optimization strategies"""
    def optimize(self, X: np.ndarray, y: np.ndarray, n_suggestions: int) -> np.ndarray:
        raise NotImplementedError

class BayesianOptimization(OptimizationStrategy):
    """Bayesian optimization with various acquisition functions"""
    def __init__(self, acquisition_fn: str = 'ei', kernel: str = 'matern'):
        self.acquisition_fn = acquisition_fn
        self.kernel = kernel
        
    def _acquisition(self, mean: np.ndarray, std: np.ndarray, y_best: float) -> np.ndarray:
        if self.acquisition_fn == 'ei':
            return expected_improvement(mean, std, y_best)
        elif self.acquisition_fn == 'ucb':
            return mean - 2.0 * std
        elif self.acquisition_fn == 'pi':
            return norm.cdf((y_best - mean) / std)
        return -mean

class RandomForestOptimization(OptimizationStrategy):
    """Random Forest based optimization"""
    def __init__(self, n_estimators: int = 100):
        self.n_estimators = n_estimators
        
    def optimize(self, X: np.ndarray, y: np.ndarray, n_suggestions: int) -> np.ndarray:
        rf = RandomForestRegressor(n_estimators=self.n_estimators)
        rf.fit(X, y)
        candidates = latin_hypercube(n_suggestions * 10, X.shape[1])
        predictions = rf.predict(candidates)
        return candidates[np.argsort(predictions)[:n_suggestions]]

class NeuralOptimization(OptimizationStrategy):
    """Neural network based optimization"""
    def __init__(self, hidden_layers: Tuple[int, ...] = (100, 50)):
        self.hidden_layers = hidden_layers
        
    def optimize(self, X: np.ndarray, y: np.ndarray, n_suggestions: int) -> np.ndarray:
        nn = MLPRegressor(hidden_layer_sizes=self.hidden_layers)
        nn.fit(X, y)
        candidates = latin_hypercube(n_suggestions * 10, X.shape[1])
        predictions = nn.predict(candidates)
        return candidates[np.argsort(predictions)[:n_suggestions]]

class HardwareConstraintOptimizer:
    def __init__(self, cache_dir: Optional[str] = None, 
                 optimization_strategy: str = 'bayesian',
                 surrogate_weight: float = 0.5,
                 use_robust_scaling: bool = False):
        # Define parameter domains with extended capabilities
        self.domains = {
            'CLOCK_PERIOD': {
                'type': 'float',
                'range': None,  # No fixed range
                'constraints': [],
                'dependencies': {}
            },
            'CORE_UTIL': {
                'type': 'int',
                'range': [20, 99],
                'constraints': [],
                'dependencies': {}
            },
            'GP_PAD': {
                'type': 'int',
                'range': [0, 4],
                'constraints': [],
                'dependencies': {}
            },
            'DP_PAD': {
                'type': 'int',
                'range': [0, 4],
                'constraints': [],
                'dependencies': {}
            },
            'ENABLE_DPO': {
                'type': 'int',
                'range': [0, 1],
                'constraints': [],
                'dependencies': {}
            },
            'PIN_LAYER_ADJUST': {
                'type': 'float',
                'range': [0.2, 0.7],
                'constraints': [],
                'dependencies': {}
            },
            'ABOVE_LAYER_ADJUST': {
                'type': 'float',
                'range': [0.2, 0.7],
                'constraints': [],
                'dependencies': {}
            },
            'PLACE_DENSITY_LB_ADDON': {
                'type': 'float',
                'range': [0.00, 0.99],
                'constraints': [],
                'dependencies': {'CORE_UTIL': lambda x, cu: x <= (100-cu)/100}
            },
            'FLATTEN': {
                'type': 'int',
                'range': [0, 1],
                'constraints': [],
                'dependencies': {}
            },
            'CTS_CLUSTER_SIZE': {
                'type': 'int',
                'range': [10, 40],
                'constraints': [],
                'dependencies': {}
            },
            'CTS_CLUSTER_DIAMETER': {
                'type': 'int',
                'range': [80, 120],
                'constraints': [],
                'dependencies': {}
            },
            'TNS_END_PERCENT': {
                'type': 'int',
                'range': [0, 100],
                'constraints': [],
                'dependencies': {}
            }
        }
        
        self.param_names = list(self.domains.keys())
        self.n_params = len(self.param_names)
        
        # Initialize scalers with option for robust scaling
        scaler_class = RobustScaler if use_robust_scaling else MinMaxScaler
        self.scalers = {name: scaler_class() for name in self.param_names}
        
        # Setup optimization strategy
        self.optimization_strategy = optimization_strategy
        self.surrogate_weight = surrogate_weight
        
        # Initialize Anthropic client with error handling
        try:
            self.client = anthropic.Anthropic()
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            self.client = None
            
        # Setup caching with versioning
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".hardware_opt_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load cached recommendations and models
        self.cached_recommendations = self._load_cached_recommendations()
        self.cached_models = self._load_cached_models()
        
    def _load_cached_models(self) -> Dict[str, Any]:
        """Load cached optimization models"""
        models_dir = self.cache_dir / "models"
        models_dir.mkdir(exist_ok=True)
        cached_models = {}
        for model_file in models_dir.glob("*.joblib"):
            try:
                cached_models[model_file.stem] = joblib.load(model_file)
            except Exception as e:
                logger.warning(f"Failed to load model {model_file}: {e}")
        return cached_models
    
    def _save_model(self, model: Any, key: str):
        """Save model to cache"""
        try:
            model_path = self.cache_dir / "models" / f"{key}.joblib"
            joblib.dump(model, model_path)
        except Exception as e:
            logger.warning(f"Failed to save model: {e}")
    
    def add_constraint(self, param_name: str, constraint_func: Callable[[float], bool], 
                      description: str):
        """Add a new constraint to a parameter"""
        if param_name in self.domains:
            self.domains[param_name]['constraints'].append({
                'func': constraint_func,
                'description': description
            })
    
    def add_dependency(self, param_name: str, dependent_param: str, 
                      dependency_func: Callable[[float, float], bool]):
        """Add a parameter dependency"""
        if param_name in self.domains and dependent_param in self.domains:
            self.domains[param_name]['dependencies'][dependent_param] = dependency_func
    
    def _validate_parameters(self, params: Dict[str, float]) -> bool:
        """Enhanced parameter validation with constraints and dependencies"""
        for name, value in params.items():
            if name not in self.domains:
                logger.error(f"Unknown parameter: {name}")
                return False
            
            domain = self.domains[name]
            
            # Range validation
            if domain['range'] is not None:
                min_val, max_val = domain['range']
                if value < min_val or value > max_val:
                    logger.error(f"Parameter {name} value {value} outside range [{min_val}, {max_val}]")
                    return False
            
            # Type validation
            if domain['type'] == 'int' and not float(value).is_integer():
                logger.error(f"Parameter {name} should be integer, got {value}")
                return False
            
            # Constraint validation
            for constraint in domain['constraints']:
                if not constraint['func'](value):
                    logger.error(f"Parameter {name} failed constraint: {constraint['description']}")
                    return False
            
            # Dependency validation
            for dep_param, dep_func in domain['dependencies'].items():
                if dep_param in params and not dep_func(value, params[dep_param]):
                    logger.error(f"Parameter {name} failed dependency with {dep_param}")
                    return False
        
        return True
    
    def _get_optimization_strategy(self) -> OptimizationStrategy:
        """Get the appropriate optimization strategy"""
        if self.optimization_strategy == 'bayesian':
            return BayesianOptimization()
        elif self.optimization_strategy == 'random_forest':
            return RandomForestOptimization()
        elif self.optimization_strategy == 'neural':
            return NeuralOptimization()
        else:
            logger.warning(f"Unknown strategy {self.optimization_strategy}, falling back to Bayesian")
            return BayesianOptimization()
    
    def _get_llm_recommendations(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Get LLM recommendations for parameter tuning strategy"""
        if not self.client:
            return {}
            
        # Analyze data distribution and structure
        dist_summary = inspect_data_distribution(X, y)
        struct_summary = inspect_data_structure(X, y, self.param_names)
        
        # Generate prompt for LLM
        prompt = generate_llm_prompt(dist_summary, struct_summary)
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2048,
                messages=[{
                    "role": "user", 
                    "content": prompt
                }]
            )
            
            # Parse LLM response into configuration
            configs = parse_llm_response(response.content[0].text)
            return configs
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {}

    def optimize_with_surrogate(self, X: np.ndarray, y: np.ndarray,
                              surrogate_values: Optional[np.ndarray] = None,
                              n_suggestions: int = 25,
                              exploration_ratio: float = 0.2) -> List[Dict[str, float]]:
        """Enhanced optimization with LLM-guided parameter tuning"""
        try:
            # Get LLM recommendations
            llm_configs = self._get_llm_recommendations(X, y)
            
            # Update optimization strategy based on LLM recommendations
            if llm_configs.get('optimization_strategy'):
                self.optimization_strategy = llm_configs['optimization_strategy']
            
            # Update exploration ratio if recommended
            if llm_configs.get('exploration_ratio'):
                exploration_ratio = llm_configs['exploration_ratio']
            
            # Scale input parameters
            X_scaled = self._scale_params(X)
            
            # Get optimization strategy
            strategy = self._get_optimization_strategy()
            
            # Split suggestions between exploration and exploitation
            n_explore = int(n_suggestions * exploration_ratio)
            n_exploit = n_suggestions - n_explore
            
            # Get exploitation suggestions
            exploit_candidates = strategy.optimize(X_scaled, y, n_exploit)
            
            # Get exploration suggestions using Latin Hypercube
            explore_candidates = latin_hypercube(n_explore, self.n_params)
            
            # Apply LLM parameter constraints if available
            if llm_configs.get('parameter_constraints'):
                for param, constraint in llm_configs['parameter_constraints'].items():
                    if param in self.domains:
                        self.add_constraint(param, constraint['func'], constraint['description'])
            
            # Combine candidates
            candidates = np.vstack([exploit_candidates, explore_candidates])
            
            # Convert to original parameter ranges and validate
            selected_params = self._unscale_params(candidates)
            
            # Convert to list of dictionaries with validation
            suggestions = []
            for i in range(n_suggestions):
                suggestion = {}
                for j, name in enumerate(self.param_names):
                    suggestion[name] = float(selected_params[i, j])
                
                if self._validate_parameters(suggestion):
                    suggestions.append(suggestion)
                else:
                    logger.warning(f"Invalid suggestion {i}, trying fallback")
                    fallback = self._generate_fallback_suggestion()
                    if fallback:
                        suggestions.append(fallback)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            return self._generate_fallback_suggestions(n_suggestions)
    
    def _generate_fallback_suggestion(self) -> Optional[Dict[str, float]]:
        """Generate a safe fallback suggestion"""
        for _ in range(10):  # Try 10 times
            suggestion = {}
            for name, domain in self.domains.items():
                if domain['range'] is not None:
                    min_val, max_val = domain['range']
                    # Use middle of range for safety
                    val = (min_val + max_val) / 2
                    if domain['type'] == 'int':
                        val = int(val)
                    suggestion[name] = val
                else:
                    suggestion[name] = 1.0  # Safe default for CLOCK_PERIOD
            
            if self._validate_parameters(suggestion):
                return suggestion
        
        return None 