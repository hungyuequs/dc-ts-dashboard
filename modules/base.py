"""
Base analysis module class for the DC Test Structure Analysis Dashboard.

This module provides the base AnalysisModule class that all analysis modules
should inherit from to ensure consistent interface and functionality.
"""


class AnalysisModule:
    """Base class for analysis modules"""
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        self.name = name
        self.db_manager = db_manager
        self.data_processor = data_processor
        self.key_prefix = key_prefix or name.replace(" ", "_").lower()
    
    def get_key(self, widget_name):
        """Generate unique key for widgets to prevent conflicts across modules"""
        return f"{self.key_prefix}_{widget_name}"
    
    def render(self, df, **kwargs):
        """Override in subclasses"""
        raise NotImplementedError(f"render method must be implemented in {self.__class__.__name__}")