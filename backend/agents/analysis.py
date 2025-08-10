"""
Analysis agent for handling data analysis and visualization tasks.
"""

import logging
import json
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseAgent
from .models import AgentTask, AgentResult, AgentPersonality, AgentType

logger = logging.getLogger(__name__)

class AnalysisAgent(BaseAgent):
    """Specialized agent for data analysis and visualization."""
    
    def __init__(self, agent_id: str):
        """Initialize analysis agent."""
        personality = AgentPersonality(
            name="Data Analysis Specialist",
            description="Expert in data analysis, statistics, and visualization",
            communication_style="analytical",
            expertise_areas=["data_analysis", "statistics", "visualization", "pattern_recognition"],
            response_patterns={
                "greeting": "I'll analyze your data and provide insights with visualizations.",
                "no_data": "I need data to analyze. Please provide a dataset or query results.",
                "analysis_complete": "Analysis complete. Here are the key insights and visualizations."
            }
        )
        
        super().__init__(agent_id, AgentType.ANALYSIS, personality)
    
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle analysis tasks."""
        task_type = task.task_type.lower()
        return any(keyword in task_type for keyword in [
            "analyze", "analysis", "statistics", "visualize", "chart", "plot", 
            "trend", "pattern", "correlation", "summary", "insights"
        ])
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process data analysis task."""
        start_time = datetime.utcnow()
        
        try:
            # Extract analysis parameters
            data = task.input_data.get("data")
            analysis_type = task.input_data.get("analysis_type", "summary")
            query = task.input_data.get("query", "")
            
            if not data:
                return AgentResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    success=False,
                    error_message="No data provided for analysis"
                )
            
            # Convert data to DataFrame if needed
            df = await self._prepare_dataframe(data)
            
            # Perform analysis based on type
            analysis_results = await self._perform_analysis(df, analysis_type, query)
            
            # Generate visualizations if applicable
            visualizations = await self._generate_visualizations(df, analysis_type)
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Calculate confidence score
            confidence_score = self._calculate_analysis_confidence(df, analysis_results)
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result_data={
                    "analysis": analysis_results,
                    "visualizations": visualizations,
                    "data_summary": {
                        "rows": len(df),
                        "columns": len(df.columns),
                        "data_types": df.dtypes.to_dict()
                    }
                },
                execution_time=execution_time,
                confidence_score=confidence_score,
                metadata={
                    "analysis_type": analysis_type,
                    "data_shape": df.shape,
                    "visualization_count": len(visualizations)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in analysis agent: {str(e)}")
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                error_message=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def _prepare_dataframe(self, data: Any) -> pd.DataFrame:
        """Convert input data to pandas DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, dict):
            return pd.DataFrame(data)
        elif isinstance(data, list):
            if data and isinstance(data[0], dict):
                return pd.DataFrame(data)
            else:
                return pd.DataFrame({"values": data})
        elif isinstance(data, str):
            # Try to parse as JSON or CSV
            try:
                parsed_data = json.loads(data)
                return pd.DataFrame(parsed_data)
            except json.JSONDecodeError:
                # Try as CSV
                from io import StringIO
                return pd.read_csv(StringIO(data))
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")
    
    async def _perform_analysis(self, df: pd.DataFrame, analysis_type: str, query: str) -> Dict[str, Any]:
        """Perform the requested analysis."""
        results = {}
        
        if analysis_type == "summary" or "summary" in query.lower():
            results["summary"] = await self._generate_summary_statistics(df)
        
        if analysis_type == "correlation" or "correlation" in query.lower():
            results["correlation"] = await self._analyze_correlations(df)
        
        if analysis_type == "trends" or "trend" in query.lower():
            results["trends"] = await self._analyze_trends(df)
        
        if analysis_type == "outliers" or "outlier" in query.lower():
            results["outliers"] = await self._detect_outliers(df)
        
        if analysis_type == "distribution" or "distribution" in query.lower():
            results["distribution"] = await self._analyze_distributions(df)
        
        # Default to summary if no specific analysis requested
        if not results:
            results["summary"] = await self._generate_summary_statistics(df)
        
        return results
    
    async def _generate_summary_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary statistics for the dataset."""
        summary = {
            "shape": df.shape,
            "columns": list(df.columns),
            "data_types": df.dtypes.to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "numeric_summary": {},
            "categorical_summary": {}
        }
        
        # Numeric columns summary
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            summary["numeric_summary"] = df[numeric_cols].describe().to_dict()
        
        # Categorical columns summary
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            summary["categorical_summary"][col] = {
                "unique_values": df[col].nunique(),
                "top_values": df[col].value_counts().head(5).to_dict()
            }
        
        return summary
    
    async def _analyze_correlations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze correlations between numeric columns."""
        numeric_df = df.select_dtypes(include=[np.number])
        
        if numeric_df.empty:
            return {"message": "No numeric columns found for correlation analysis"}
        
        correlation_matrix = numeric_df.corr()
        
        # Find strong correlations (> 0.7 or < -0.7)
        strong_correlations = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                corr_value = correlation_matrix.iloc[i, j]
                if abs(corr_value) > 0.7:
                    strong_correlations.append({
                        "column1": correlation_matrix.columns[i],
                        "column2": correlation_matrix.columns[j],
                        "correlation": corr_value
                    })
        
        return {
            "correlation_matrix": correlation_matrix.to_dict(),
            "strong_correlations": strong_correlations
        }
    
    async def _analyze_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze trends in time series or sequential data."""
        trends = {}
        
        # Look for date/time columns
        date_cols = df.select_dtypes(include=['datetime64']).columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            date_col = date_cols[0]
            df_sorted = df.sort_values(date_col)
            
            for num_col in numeric_cols:
                # Calculate trend (simple linear regression slope)
                x = np.arange(len(df_sorted))
                y = df_sorted[num_col].values
                
                # Remove NaN values
                mask = ~np.isnan(y)
                if mask.sum() > 1:
                    slope = np.polyfit(x[mask], y[mask], 1)[0]
                    trends[num_col] = {
                        "slope": slope,
                        "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
                    }
        
        return trends if trends else {"message": "No time series data found for trend analysis"}
    
    async def _detect_outliers(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect outliers using IQR method."""
        outliers = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_count = outlier_mask.sum()
            
            if outlier_count > 0:
                outliers[col] = {
                    "count": int(outlier_count),
                    "percentage": float(outlier_count / len(df) * 100),
                    "bounds": {"lower": lower_bound, "upper": upper_bound}
                }
        
        return outliers
    
    async def _analyze_distributions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze distributions of numeric columns."""
        distributions = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            distributions[col] = {
                "mean": float(df[col].mean()),
                "median": float(df[col].median()),
                "std": float(df[col].std()),
                "skewness": float(df[col].skew()),
                "kurtosis": float(df[col].kurtosis())
            }
        
        return distributions
    
    async def _generate_visualizations(self, df: pd.DataFrame, analysis_type: str) -> List[Dict[str, Any]]:
        """Generate visualization recommendations."""
        visualizations = []
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        
        # Histogram for numeric columns
        if len(numeric_cols) > 0:
            visualizations.append({
                "type": "histogram",
                "title": "Distribution of Numeric Variables",
                "columns": list(numeric_cols),
                "description": "Shows the distribution of numeric variables"
            })
        
        # Bar chart for categorical columns
        if len(categorical_cols) > 0:
            visualizations.append({
                "type": "bar_chart",
                "title": "Categorical Variable Counts",
                "columns": list(categorical_cols),
                "description": "Shows the frequency of categorical variables"
            })
        
        # Correlation heatmap if multiple numeric columns
        if len(numeric_cols) > 1:
            visualizations.append({
                "type": "heatmap",
                "title": "Correlation Matrix",
                "columns": list(numeric_cols),
                "description": "Shows correlations between numeric variables"
            })
        
        # Scatter plot for pairs of numeric columns
        if len(numeric_cols) >= 2:
            visualizations.append({
                "type": "scatter_plot",
                "title": "Scatter Plot Matrix",
                "columns": list(numeric_cols[:2]),  # First two numeric columns
                "description": "Shows relationships between numeric variables"
            })
        
        return visualizations
    
    def _calculate_analysis_confidence(self, df: pd.DataFrame, results: Dict[str, Any]) -> float:
        """Calculate confidence score for the analysis."""
        confidence_factors = []
        
        # Data quality factor
        missing_ratio = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])
        data_quality = 1.0 - missing_ratio
        confidence_factors.append(data_quality)
        
        # Sample size factor
        sample_size_factor = min(len(df) / 100.0, 1.0)  # Optimal around 100+ rows
        confidence_factors.append(sample_size_factor)
        
        # Analysis completeness factor
        analysis_completeness = len(results) / 5.0  # Assuming 5 possible analysis types
        confidence_factors.append(min(analysis_completeness, 1.0))
        
        # Average confidence
        return sum(confidence_factors) / len(confidence_factors)