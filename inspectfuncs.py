#!/usr/bin/env python3

import numpy as np
from typing import Dict, Any, Optional, Tuple
from scipy import stats
from sklearn.manifold import TSNE, MDS
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import LocalOutlierFactor
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN, KMeans
from scipy.spatial.distance import pdist, squareform
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from scipy.stats import f_oneway

def analyze_manifold_structure(X: np.ndarray, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze the underlying manifold structure of the data"""
    default_config = {
        "n_components": 2,
        "perplexity": min(30, max(5, len(X) - 1)),
        "n_iter": 1000,
        "learning_rate": "auto"
    }
    
    if config is not None:
        default_config.update(config)
    config = default_config
    
    summary = {}
    
    # PCA to check linear structure
    pca = PCA()
    X_scaled = StandardScaler().fit_transform(X)
    pca.fit(X_scaled)
    explained_var_ratio = pca.explained_variance_ratio_
    summary["pca_explained_variance"] = explained_var_ratio.tolist()
    summary["linear_dimensionality"] = np.sum(np.cumsum(explained_var_ratio) < 0.95) + 1
    
    # TSNE for nonlinear structure
    if len(X) > config["n_components"]:
        try:
            tsne = TSNE(
                n_components=config["n_components"],
                perplexity=config["perplexity"],
                n_iter=config["n_iter"],
                learning_rate=config["learning_rate"]
            )
            X_tsne = tsne.fit_transform(X_scaled)
            
            # Analyze TSNE embedding
            distances = pdist(X_tsne)
            summary["tsne_avg_distance"] = float(np.mean(distances))
            summary["tsne_std_distance"] = float(np.std(distances))
        except Exception as e:
            summary["tsne_error"] = str(e)
    else:
        summary["tsne_error"] = "Not enough samples for TSNE"
    
    # MDS stress analysis
    if len(X) > config["n_components"]:
        try:
            mds = MDS(n_components=config["n_components"], normalized_stress='auto')
            mds.fit_transform(X_scaled)
            summary["mds_stress"] = float(mds.stress_)
        except Exception as e:
            summary["mds_error"] = str(e)
    else:
        summary["mds_error"] = "Not enough samples for MDS"
    
    return summary

def analyze_local_structure(X: np.ndarray, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze the local structure and patterns in the data"""
    default_config = {
        "n_neighbors": min(20, len(X) - 1),
        "contamination": 0.1,
        "eps": None,  # Auto-compute for DBSCAN
        "min_samples": 5
    }
    
    if config is not None:
        default_config.update(config)
    config = default_config
    
    summary = {}
    
    # Local Outlier Factor analysis
    try:
        lof = LocalOutlierFactor(
            n_neighbors=config["n_neighbors"],
            contamination=config["contamination"]
        )
        outlier_labels = lof.fit_predict(X)
        summary["outlier_ratio"] = float(np.mean(outlier_labels == -1))
        summary["negative_outlier_factor"] = float(np.mean(-lof.negative_outlier_factor_))
    except Exception as e:
        summary["lof_error"] = str(e)
    
    # DBSCAN clustering for density analysis
    try:
        if config["eps"] is None:
            # Compute reasonable eps based on data
            distances = pdist(X)
            config["eps"] = np.percentile(distances, 10)  # 10th percentile of distances
        
        dbscan = DBSCAN(eps=config["eps"], min_samples=config["min_samples"])
        cluster_labels = dbscan.fit_predict(X)
        
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        noise_ratio = np.mean(cluster_labels == -1)
        
        summary.update({
            "n_density_clusters": n_clusters,
            "noise_ratio": float(noise_ratio),
            "eps_used": float(config["eps"])
        })
    except Exception as e:
        summary["dbscan_error"] = str(e)
    
    return summary

def inspect_data_distribution(X: np.ndarray, Y: np.ndarray, Y_surrogate: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """Analyze the statistical properties of input and output data"""
    summary = {}
    
    # Input space analysis
    summary["n_samples"] = len(X)
    summary["n_features"] = X.shape[1]
    summary["feature_ranges"] = [(float(np.min(X[:, i])), float(np.max(X[:, i]))) for i in range(X.shape[1])]
    summary["feature_spreads"] = [float(np.std(X[:, i])) for i in range(X.shape[1])]
    
    # Feature distribution analysis
    for i in range(X.shape[1]):
        summary[f"feature_{i}_skew"] = float(stats.skew(X[:, i]))
        summary[f"feature_{i}_kurtosis"] = float(stats.kurtosis(X[:, i]))
        if len(X) > 20:  # Only if enough samples
            _, p_value = stats.normaltest(X[:, i])
            summary[f"feature_{i}_normality_p"] = float(p_value)
    
    # Output analysis
    summary["y_missing_ratio"] = float(np.mean(np.isnan(Y)))
    valid_Y = Y[~np.isnan(Y)]
    if len(valid_Y) > 0:
        summary["y_range"] = (float(np.min(valid_Y)), float(np.max(valid_Y)))
        summary["y_spread"] = float(np.std(valid_Y))
        summary["y_skew"] = float(stats.skew(valid_Y))
        summary["y_kurtosis"] = float(stats.kurtosis(valid_Y))
        if len(valid_Y) > 20:
            _, p_value = stats.normaltest(valid_Y)
            summary["y_normality_p"] = float(p_value)
    
    # Surrogate analysis
    if Y_surrogate is not None:
        summary["has_surrogate"] = True
        valid_both_mask = ~np.isnan(Y) & ~np.isnan(Y_surrogate)
        if np.sum(valid_both_mask) > 1:
            correlation = np.corrcoef(Y[valid_both_mask], Y_surrogate[valid_both_mask])[0,1]
            summary["surrogate_correlation"] = float(correlation)
            # Analyze surrogate error distribution
            errors = Y_surrogate[valid_both_mask] - Y[valid_both_mask]
            summary["surrogate_bias"] = float(np.mean(errors))
            summary["surrogate_error_std"] = float(np.std(errors))
            if len(errors) > 20:
                _, p_value = stats.normaltest(errors)
                summary["surrogate_error_normality_p"] = float(p_value)
    else:
        summary["has_surrogate"] = False
    
    return summary

def inspect_data_structure(X: np.ndarray, Y: np.ndarray, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze the structural properties of the data and provide model recommendations"""
    if config is None:
        config = {
            "n_clusters": 5,
            "correlation_threshold": 0.5,
            "n_neighbors": 20,
            "perplexity": 30
        }
    
    summary = {}
    
    # Scale data for analysis
    X_scaled = StandardScaler().fit_transform(X)
    valid_mask = ~np.isnan(Y)
    X_valid = X_scaled[valid_mask]
    Y_valid = Y[valid_mask]
    
    # Analyze feature importance
    if len(Y_valid) > 0:
        correlations = np.array([np.abs(np.corrcoef(X_valid[:, i], Y_valid)[0, 1]) 
                               for i in range(X.shape[1])])
        summary["feature_importance"] = correlations.tolist()
        summary["important_features"] = (correlations > np.mean(correlations)).tolist()
    
    # Nonlinearity analysis
    if len(Y_valid) > 1:
        # Linear model check
        lr = LinearRegression()
        lr.fit(X_valid, Y_valid)
        linear_score = lr.score(X_valid, Y_valid)
        summary["linearity_score"] = float(linear_score)
        
        # Polynomial check
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X_valid)
        lr_poly = LinearRegression()
        lr_poly.fit(X_poly, Y_valid)
        poly_score = lr_poly.score(X_poly, Y_valid)
        summary["polynomial_score"] = float(poly_score)
        
        # Determine if relationship is strongly nonlinear
        summary["is_nonlinear"] = bool(poly_score - linear_score > 0.1)
    
    # Clustering analysis for local patterns
    n_clusters = min(config["n_clusters"], len(X))
    kmeans = KMeans(n_clusters=n_clusters, n_init=10)
    cluster_labels = kmeans.fit_predict(X_valid)
    
    # Analyze cluster characteristics
    cluster_sizes = [np.sum(cluster_labels == i) for i in range(n_clusters)]
    summary["cluster_sizes"] = cluster_sizes
    summary["cluster_balance"] = float(np.std(cluster_sizes) / np.mean(cluster_sizes))
    
    # Check if clusters have significantly different Y distributions
    if len(Y_valid) > 0:
        cluster_y_means = [np.mean(Y_valid[cluster_labels == i]) for i in range(n_clusters)]
        cluster_y_stds = [np.std(Y_valid[cluster_labels == i]) for i in range(n_clusters)]
        summary["cluster_y_means"] = cluster_y_means
        summary["cluster_y_stds"] = cluster_y_stds
        
        # Test if clusters are significantly different
        try:
            cluster_samples = [Y_valid[cluster_labels == i] for i in range(n_clusters)]
            f_stat, p_value = f_oneway(*[s for s in cluster_samples if len(s) > 0])
            summary["clusters_different_pvalue"] = float(p_value)
            summary["needs_local_models"] = bool(p_value < 0.05)
        except:
            summary["needs_local_models"] = False
    
    # Feature correlations
    if X.shape[1] > 1:
        correlations = np.corrcoef(X_valid.T)
        high_corr = np.abs(correlations) > config["correlation_threshold"]
        np.fill_diagonal(high_corr, False)
        summary["high_correlation_pairs"] = int(np.sum(high_corr) / 2)
        summary["has_correlated_features"] = bool(np.sum(high_corr) > 0)
    
    # Add manifold analysis
    manifold_summary = analyze_manifold_structure(X_valid, config)
    summary.update(manifold_summary)
    
    # Add local structure analysis
    local_summary = analyze_local_structure(X_valid, config)
    summary.update(local_summary)
    
    # Make model recommendations
    recommendations = {}
    
    # Kernel type recommendation
    if summary.get("is_nonlinear", False):
        if summary.get("has_correlated_features", False):
            recommendations["kernel_type"] = "rational"  # RationalQuadratic handles correlations well
        else:
            recommendations["kernel_type"] = "composite"  # Composite kernel for complex patterns
    else:
        recommendations["kernel_type"] = "matern"  # Matern for simpler patterns
    
    # Other model parameters
    recommendations["needs_feature_scaling"] = True
    recommendations["needs_local_models"] = summary.get("needs_local_models", False)
    if "important_features" in summary:
        recommendations["use_feature_weights"] = True
        recommendations["feature_weights"] = summary["feature_importance"]
    
    summary["model_recommendations"] = recommendations
    
    return summary 