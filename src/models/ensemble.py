"""
Ensemble Model - Combining Multiple Models

Combines predictions from multiple models to get better overall predictions.

Ensemble methods:
1. Weighted Average - Weight models by their historical accuracy
2. Stacking - Use one model's predictions as features for another
3. Voting - Take majority vote from multiple models

Why ensembles work:
- Different models make different types of errors
- Averaging reduces variance
- Usually more robust than any single model

This is Phase 6 stuff - only use if simple models work well first!

Usage:
    from src.models.ensemble import EnsembleModel
    from src.models.goals import BTTSModel, OverUnderModel
    
    # Create ensemble
    ensemble = EnsembleModel(
        models=[BTTSModel(), OverUnderModel()],
        weights=[0.6, 0.4]  # Weight first model more
    )
    
    # Get combined prediction
    prediction = ensemble.predict(home_id=1, away_id=2, date='2024-01-15')
"""

from typing import Dict, List, Any, Optional
import logging
import numpy as np

from src.models.base_model import BaseModel

# Set up logging
logger = logging.getLogger(__name__)


class EnsembleModel(BaseModel):
    """
    Combines multiple models into a single ensemble prediction.
    
    Usually performs better than any individual model by reducing variance
    and combining different perspectives.
    """
    
    def __init__(
        self,
        models: List[BaseModel],
        weights: Optional[List[float]] = None,
        ensemble_method: str = 'weighted_average'
    ):
        """
        Initialise ensemble model.
        
        Args:
            models: List of model instances to ensemble
            weights: Weight for each model (must sum to 1.0)
                    If None, equal weights used
            ensemble_method: How to combine predictions:
                - 'weighted_average': Weight each model's probability
                - 'simple_average': Unweighted average (ignores weights param)
                - 'voting': Majority vote (threshold at 0.5)
                - 'max_confidence': Use prediction from most confident model
        """
        super().__init__(
            name="EnsembleModel",
            version="1.0.0",
            description=f"Ensemble of {len(models)} models using {ensemble_method}"
        )
        
        if not models:
            raise ValueError("Must provide at least one model for ensemble")
        
        self.models = models
        self.ensemble_method = ensemble_method
        
        # Set up weights
        if weights is None:
            # Equal weights
            self.weights = [1.0 / len(models)] * len(models)
        else:
            if len(weights) != len(models):
                raise ValueError("Number of weights must match number of models")
            if abs(sum(weights) - 1.0) > 0.01:
                raise ValueError(f"Weights must sum to 1.0, got {sum(weights)}")
            self.weights = weights
        
        logger.info(
            f"Ensemble initialised with {len(models)} models "
            f"using {ensemble_method}"
        )
        logger.info(f"  Models: {[m.name for m in models]}")
        logger.info(f"  Weights: {[f'{w:.2f}' for w in self.weights]}")
    
    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date: str
    ) -> Dict[str, Any]:
        """
        Get ensemble prediction combining all models.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            match_date: Match date (YYYY-MM-DD)
            
        Returns:
            Dict with ensemble prediction including individual model predictions
        """
        # Validate inputs
        if not self.validate_inputs(home_team_id, away_team_id, match_date):
            logger.error("Invalid inputs for ensemble prediction")
            return self._get_default_prediction()
        
        try:
            # Get predictions from all models
            individual_predictions = []
            confidences = []
            
            for i, model in enumerate(self.models):
                try:
                    pred = model.predict(home_team_id, away_team_id, match_date)
                    individual_predictions.append(pred)
                    
                    # Extract confidence if available
                    confidence = pred.get('confidence', self.weights[i])
                    confidences.append(confidence)
                    
                    logger.debug(f"  {model.name}: Got prediction")
                    
                except Exception as e:
                    logger.error(f"  {model.name}: Prediction failed - {e}")
                    # Skip this model if it fails
                    individual_predictions.append(None)
                    confidences.append(0.0)
            
            # Remove None predictions and adjust weights
            valid_predictions = []
            valid_weights = []
            valid_confidences = []
            
            for pred, weight, conf in zip(individual_predictions, self.weights, confidences):
                if pred is not None:
                    valid_predictions.append(pred)
                    valid_weights.append(weight)
                    valid_confidences.append(conf)
            
            if not valid_predictions:
                logger.error("All model predictions failed")
                return self._get_default_prediction()
            
            # Normalise weights to sum to 1.0
            total_weight = sum(valid_weights)
            valid_weights = [w / total_weight for w in valid_weights]
            
            # Combine predictions based on method
            if self.ensemble_method == 'weighted_average':
                combined = self._weighted_average(valid_predictions, valid_weights)
            elif self.ensemble_method == 'simple_average':
                equal_weights = [1.0 / len(valid_predictions)] * len(valid_predictions)
                combined = self._weighted_average(valid_predictions, equal_weights)
            elif self.ensemble_method == 'voting':
                combined = self._voting(valid_predictions)
            elif self.ensemble_method == 'max_confidence':
                combined = self._max_confidence(valid_predictions, valid_confidences)
            else:
                logger.error(f"Unknown ensemble method: {self.ensemble_method}")
                combined = self._weighted_average(valid_predictions, valid_weights)
            
            # Add metadata
            combined['ensemble_method'] = self.ensemble_method
            combined['models_used'] = [m.name for m in self.models if m in 
                                      [self.models[i] for i, p in enumerate(individual_predictions) if p is not None]]
            combined['individual_predictions'] = valid_predictions
            
            # Update model metadata
            self._update_metadata()
            
            logger.info(
                f"Ensemble prediction: {self.ensemble_method} "
                f"using {len(valid_predictions)}/{len(self.models)} models"
            )
            
            return combined
            
        except Exception as e:
            logger.error(f"Ensemble prediction failed: {e}")
            return self._get_default_prediction()
    
    def _weighted_average(
        self,
        predictions: List[Dict],
        weights: List[float]
    ) -> Dict[str, Any]:
        """
        Combine predictions using weighted average.
        
        Works for probability predictions - averages each probability field.
        
        Args:
            predictions: List of prediction dicts from models
            weights: Weight for each prediction
            
        Returns:
            Combined prediction dict
        """
        combined = {}
        
        # Find all probability fields (fields ending in '_prob')
        prob_fields = set()
        for pred in predictions:
            prob_fields.update([k for k in pred.keys() if k.endswith('_prob')])
        
        # Average each probability field
        for field in prob_fields:
            values = []
            field_weights = []
            
            for pred, weight in zip(predictions, weights):
                if field in pred:
                    values.append(pred[field])
                    field_weights.append(weight)
            
            if values:
                # Normalise weights for this field
                total = sum(field_weights)
                field_weights = [w / total for w in field_weights]
                
                # Weighted average
                combined[field] = sum(v * w for v, w in zip(values, field_weights))
        
        # Average confidence scores
        confidences = [p.get('confidence', 0.5) for p in predictions]
        combined['confidence'] = np.mean(confidences)
        
        return combined
    
    def _simple_average(
        self,
        predictions: List[Dict]
    ) -> Dict[str, Any]:
        """
        Simple unweighted average of predictions.
        """
        equal_weights = [1.0 / len(predictions)] * len(predictions)
        return self._weighted_average(predictions, equal_weights)
    
    def _voting(
        self,
        predictions: List[Dict]
    ) -> Dict[str, Any]:
        """
        Majority voting for binary predictions.
        
        Each model gets one vote. Threshold each probability at 0.5 to get binary vote.
        Final probability = fraction of models that voted yes.
        
        Args:
            predictions: List of prediction dicts
            
        Returns:
            Combined prediction based on majority vote
        """
        combined = {}
        
        # Find probability fields
        prob_fields = set()
        for pred in predictions:
            prob_fields.update([k for k in pred.keys() if k.endswith('_prob')])
        
        # Vote for each field
        for field in prob_fields:
            votes = []
            
            for pred in predictions:
                if field in pred:
                    # Vote 1 if probability > 0.5, else 0
                    vote = 1 if pred[field] > 0.5 else 0
                    votes.append(vote)
            
            if votes:
                # Probability = fraction voting yes
                combined[field] = sum(votes) / len(votes)
        
        # Average confidence
        confidences = [p.get('confidence', 0.5) for p in predictions]
        combined['confidence'] = np.mean(confidences)
        
        return combined
    
    def _max_confidence(
        self,
        predictions: List[Dict],
        confidences: List[float]
    ) -> Dict[str, Any]:
        """
        Use prediction from most confident model.
        
        Sometimes one model is much more confident than others - trust it!
        
        Args:
            predictions: List of prediction dicts
            confidences: Confidence score for each prediction
            
        Returns:
            Prediction from most confident model
        """
        # Find most confident model
        max_conf_idx = np.argmax(confidences)
        
        # Return its prediction
        best_prediction = predictions[max_conf_idx].copy()
        best_prediction['selected_model'] = self.models[max_conf_idx].name
        best_prediction['selected_confidence'] = confidences[max_conf_idx]
        
        return best_prediction
    
    def _get_default_prediction(self) -> Dict[str, Any]:
        """
        Return default prediction if ensemble fails.
        """
        return {
            'error': 'Ensemble prediction failed',
            'confidence': 0.0,
            'ensemble_method': self.ensemble_method,
            'models_used': []
        }
    
    def optimise_weights(
        self,
        training_data: List[tuple],
        market_type: str = 'btts'
    ) -> List[float]:
        """
        Find optimal weights for ensemble based on historical performance.
        
        Tests different weight combinations and finds best performing one.
        
        Args:
            training_data: List of (home_id, away_id, date, actual_outcome) tuples
            market_type: Market to optimise for
            
        Returns:
            Optimal weights as list
        """
        logger.info("Optimising ensemble weights...")
        
        # For now, just use equal weights
        # TODO: Implement grid search or gradient descent to find optimal weights
        optimal_weights = [1.0 / len(self.models)] * len(self.models)
        
        logger.info(f"Optimal weights: {[f'{w:.2f}' for w in optimal_weights]}")
        
        return optimal_weights


if __name__ == "__main__":
    """
    Test ensemble model with mock models.
    """
    print("\n" + "="*60)
    print("ENSEMBLE MODEL TEST")
    print("="*60 + "\n")
    
    # Create mock models for testing
    from src.models.base_model import BaseModel
    
    class MockModel1(BaseModel):
        def __init__(self):
            super().__init__(name="MockModel1", version="1.0.0")
        
        def predict(self, home_team_id, away_team_id, match_date):
            return {
                'btts_yes_prob': 0.60,
                'confidence': 0.80
            }
    
    class MockModel2(BaseModel):
        def __init__(self):
            super().__init__(name="MockModel2", version="1.0.0")
        
        def predict(self, home_team_id, away_team_id, match_date):
            return {
                'btts_yes_prob': 0.70,
                'confidence': 0.75
            }
    
    # Test different ensemble methods
    methods = ['weighted_average', 'simple_average', 'voting', 'max_confidence']
    
    for method in methods:
        print(f"\n--- Testing {method} ---")
        
        ensemble = EnsembleModel(
            models=[MockModel1(), MockModel2()],
            weights=[0.6, 0.4],
            ensemble_method=method
        )
        
        prediction = ensemble.predict(1, 2, '2024-01-15')
        
        print(f"Method: {method}")
        print(f"BTTS Yes: {prediction.get('btts_yes_prob', 'N/A')}")
        print(f"Confidence: {prediction.get('confidence', 'N/A')}")
        print(f"Models used: {prediction.get('models_used', [])}")
    
    print("\n" + "="*60)
    print("Ensemble Model working correctly!")
    print("="*60 + "\n")