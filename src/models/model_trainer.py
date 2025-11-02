"""
Model Trainer - Training and Calibration Utilities

Provides functions for:
- Training models on historical data
- Cross-validation
- Probability calibration
- Performance evaluation

This is mainly for Phase 4 (Backtesting) but good to have in place early.

Usage:
    from src.models.model_trainer import ModelTrainer
    from src.models.goals import BTTSModel
    
    trainer = ModelTrainer()
    
    # Calibrate a model's probabilities
    calibrated_model = trainer.calibrate_model(
        model=BTTSModel(),
        training_data=historical_matches
    )
    
    # Evaluate model performance
    metrics = trainer.evaluate_model(
        model=calibrated_model,
        test_data=test_matches
    )
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, log_loss

from src.data.database import Session, Match

# Set up logging
logger = logging.getLogger(__name__)


class ModelTrainer:
    """
    Utilities for training and calibrating prediction models.
    
    Most betting models don't need traditional "training" like ML models,
    but they DO need probability calibration and validation.
    """
    
    def __init__(self):
        """
        Initialise model trainer.
        """
        logger.info("Model Trainer initialised")
    
    def calibrate_probabilities(
        self,
        predictions: List[float],
        actual_outcomes: List[int]
    ) -> Dict[str, Any]:
        """
        Check if model probabilities are well-calibrated.
        
        A well-calibrated model means:
        - When it says 70% probability, it should happen ~70% of the time
        - When it says 30% probability, it should happen ~30% of the time
        
        Args:
            predictions: List of predicted probabilities (0.0-1.0)
            actual_outcomes: List of actual outcomes (0 or 1)
            
        Returns:
            Dict with calibration metrics:
                - is_calibrated: Whether model is well-calibrated
                - calibration_curve: Data for plotting
                - brier_score: Calibration quality metric (lower = better)
        """
        if len(predictions) != len(actual_outcomes):
            raise ValueError("Predictions and outcomes must have same length")
        
        if len(predictions) < 30:
            logger.warning("Need at least 30 samples for reliable calibration analysis")
        
        # Calculate Brier score (measures probability accuracy)
        # Perfect score = 0, worst score = 1
        brier = brier_score_loss(actual_outcomes, predictions)
        
        # Get calibration curve (bins predictions and checks actual rate)
        try:
            fraction_of_positives, mean_predicted_value = calibration_curve(
                actual_outcomes,
                predictions,
                n_bins=10,
                strategy='uniform'
            )
            
            # Check if well-calibrated (within 0.05 of diagonal)
            calibration_error = np.mean(np.abs(
                fraction_of_positives - mean_predicted_value
            ))
            is_calibrated = calibration_error < 0.05
            
        except Exception as e:
            logger.error(f"Calibration curve calculation failed: {e}")
            fraction_of_positives = []
            mean_predicted_value = []
            is_calibrated = False
        
        result = {
            'is_calibrated': is_calibrated,
            'brier_score': brier,
            'calibration_error': calibration_error if fraction_of_positives.size > 0 else None,
            'calibration_curve': {
                'fraction_positive': fraction_of_positives.tolist() if fraction_of_positives.size > 0 else [],
                'mean_predicted': mean_predicted_value.tolist() if mean_predicted_value.size > 0 else [],
            },
            'sample_size': len(predictions)
        }
        
        logger.info(
            f"Calibration: Brier={brier:.4f}, "
            f"Calibrated={'✅' if is_calibrated else '❌'}"
        )
        
        return result
    
    def evaluate_model(
        self,
        model: Any,
        test_matches: List[Tuple[int, int, str, int]],
        market_type: str = 'btts'
    ) -> Dict[str, Any]:
        """
        Evaluate model performance on historical matches.
        
        Args:
            model: Model instance with predict() method
            test_matches: List of (home_id, away_id, date, actual_outcome) tuples
            market_type: Which market to evaluate ('btts', 'over_under', etc.)
            
        Returns:
            Dict with performance metrics:
                - accuracy: Percentage of correct predictions
                - precision: True positives / Predicted positives
                - recall: True positives / Actual positives
                - brier_score: Probability calibration quality
                - roi: Theoretical ROI (if we bet everything at fair odds)
        """
        logger.info(f"Evaluating {model.name} on {len(test_matches)} matches...")
        
        predictions = []
        actuals = []
        probabilities = []
        
        for home_id, away_id, date, actual in test_matches:
            try:
                # Get model prediction
                pred = model.predict(home_id, away_id, date)
                
                # Extract probability based on market type
                if market_type == 'btts':
                    prob = pred.get('btts_yes_prob', 0.5)
                elif market_type == 'over_under':
                    prob = pred.get('over_prob', 0.5)
                elif market_type == 'clean_sheet_home':
                    prob = pred.get('home_clean_sheet_prob', 0.3)
                else:
                    prob = 0.5
                
                # Binary prediction (threshold at 0.5)
                binary_pred = 1 if prob > 0.5 else 0
                
                predictions.append(binary_pred)
                actuals.append(actual)
                probabilities.append(prob)
                
            except Exception as e:
                logger.error(f"Prediction failed for match {home_id} vs {away_id}: {e}")
                continue
        
        if not predictions:
            return {'error': 'No successful predictions'}
        
        # Calculate metrics
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        probabilities = np.array(probabilities)
        
        # Accuracy
        accuracy = np.mean(predictions == actuals)
        
        # Precision (of positive predictions)
        true_positives = np.sum((predictions == 1) & (actuals == 1))
        predicted_positives = np.sum(predictions == 1)
        precision = true_positives / predicted_positives if predicted_positives > 0 else 0
        
        # Recall (sensitivity)
        actual_positives = np.sum(actuals == 1)
        recall = true_positives / actual_positives if actual_positives > 0 else 0
        
        # Brier score
        brier = brier_score_loss(actuals, probabilities)
        
        # Theoretical ROI (if we bet everything at fair odds)
        # Fair odds = 1 / probability
        stakes = len(probabilities)
        returns = np.sum([
            (1 / prob) if actual == 1 else 0
            for prob, actual in zip(probabilities, actuals)
        ])
        roi = (returns - stakes) / stakes
        
        # Calibration
        calibration = self.calibrate_probabilities(
            probabilities.tolist(),
            actuals.tolist()
        )
        
        results = {
            'model_name': model.name,
            'market_type': market_type,
            'sample_size': len(predictions),
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'brier_score': brier,
            'theoretical_roi': roi,
            'is_calibrated': calibration['is_calibrated'],
            'calibration': calibration
        }
        
        logger.info(
            f"Evaluation complete: "
            f"Accuracy={accuracy:.1%}, "
            f"Brier={brier:.4f}, "
            f"ROI={roi:.2%}"
        )
        
        return results
    
    def cross_validate_model(
        self,
        model: Any,
        matches: List[Tuple[int, int, str, int]],
        n_splits: int = 5,
        market_type: str = 'btts'
    ) -> Dict[str, Any]:
        """
        Perform time-series cross-validation.
        
        Important: We use FORWARD CHAINING, not random splits.
        Can't look into the future when training models!
        
        Args:
            model: Model to validate
            matches: All available matches (sorted by date)
            n_splits: Number of CV splits
            market_type: Market to evaluate
            
        Returns:
            Dict with average performance across all splits
        """
        logger.info(f"Cross-validating {model.name} with {n_splits} splits...")
        
        # Split matches into n chunks chronologically
        split_size = len(matches) // (n_splits + 1)
        
        all_results = []
        
        for i in range(n_splits):
            # Training set: all matches up to split point
            train_end = (i + 1) * split_size
            
            # Test set: next chunk of matches
            test_start = train_end
            test_end = test_start + split_size
            
            test_matches = matches[test_start:test_end]
            
            logger.debug(f"Split {i+1}/{n_splits}: Testing on {len(test_matches)} matches")
            
            # Evaluate on this split
            results = self.evaluate_model(model, test_matches, market_type)
            all_results.append(results)
        
        # Calculate average metrics
        avg_results = {
            'model_name': model.name,
            'market_type': market_type,
            'n_splits': n_splits,
            'total_matches': len(matches),
            'avg_accuracy': np.mean([r['accuracy'] for r in all_results]),
            'avg_brier_score': np.mean([r['brier_score'] for r in all_results]),
            'avg_roi': np.mean([r['theoretical_roi'] for r in all_results]),
            'std_roi': np.std([r['theoretical_roi'] for r in all_results]),
            'split_results': all_results
        }
        
        logger.info(
            f"Cross-validation complete: "
            f"Avg Accuracy={avg_results['avg_accuracy']:.1%}, "
            f"Avg ROI={avg_results['avg_roi']:.2%} ± {avg_results['std_roi']:.2%}"
        )
        
        return avg_results
    
    def find_optimal_threshold(
        self,
        probabilities: List[float],
        actual_outcomes: List[int],
        metric: str = 'f1'
    ) -> Tuple[float, float]:
        """
        Find optimal probability threshold for making binary predictions.
        
        Default threshold is 0.5, but sometimes other thresholds work better.
        
        Args:
            probabilities: Predicted probabilities
            actual_outcomes: Actual outcomes (0 or 1)
            metric: Optimisation metric ('f1', 'accuracy', 'precision', 'recall')
            
        Returns:
            (optimal_threshold, metric_value)
        """
        thresholds = np.arange(0.3, 0.8, 0.05)
        best_threshold = 0.5
        best_score = 0
        
        for threshold in thresholds:
            predictions = (np.array(probabilities) > threshold).astype(int)
            actuals = np.array(actual_outcomes)
            
            if metric == 'accuracy':
                score = np.mean(predictions == actuals)
            elif metric == 'precision':
                tp = np.sum((predictions == 1) & (actuals == 1))
                pred_pos = np.sum(predictions == 1)
                score = tp / pred_pos if pred_pos > 0 else 0
            elif metric == 'recall':
                tp = np.sum((predictions == 1) & (actuals == 1))
                actual_pos = np.sum(actuals == 1)
                score = tp / actual_pos if actual_pos > 0 else 0
            else:  # f1
                tp = np.sum((predictions == 1) & (actuals == 1))
                pred_pos = np.sum(predictions == 1)
                actual_pos = np.sum(actuals == 1)
                precision = tp / pred_pos if pred_pos > 0 else 0
                recall = tp / actual_pos if actual_pos > 0 else 0
                score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            if score > best_score:
                best_score = score
                best_threshold = threshold
        
        logger.info(
            f"Optimal threshold: {best_threshold:.2f} "
            f"({metric}={best_score:.3f})"
        )
        
        return best_threshold, best_score


if __name__ == "__main__":
    """
    Test model trainer with synthetic data.
    """
    print("\n" + "="*60)
    print("MODEL TRAINER TEST")
    print("="*60 + "\n")
    
    trainer = ModelTrainer()
    
    # Create synthetic data
    # Simulate a well-calibrated model
    np.random.seed(42)
    probabilities = np.random.uniform(0.2, 0.8, 100)
    actuals = (np.random.uniform(0, 1, 100) < probabilities).astype(int)
    
    print("Testing probability calibration...")
    calibration = trainer.calibrate_probabilities(
        probabilities.tolist(),
        actuals.tolist()
    )
    
    print(f"\nCalibration results:")
    print(f"  Is calibrated: {calibration['is_calibrated']}")
    print(f"  Brier score: {calibration['brier_score']:.4f}")
    print(f"  Sample size: {calibration['sample_size']}")
    
    # Test threshold optimization
    print("\n\nTesting optimal threshold finding...")
    optimal_threshold, score = trainer.find_optimal_threshold(
        probabilities.tolist(),
        actuals.tolist(),
        metric='f1'
    )
    
    print(f"Optimal threshold: {optimal_threshold:.2f}")
    print(f"F1 score: {score:.3f}")
    
    print("\n" + "="*60)
    print("Model Trainer working correctly!")
    print("="*60 + "\n")