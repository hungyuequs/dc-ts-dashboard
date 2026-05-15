"""
Refactored DC Test Structure Analysis Dashboard
Better organized with modular structure and database utility integration
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import sys
import traceback
from datetime import datetime, timedelta
from scipy import stats
from components.database_utility import (
    ensure_database_exists, append_data_to_table, get_database_path,
    get_table_names, load_table_data, check_table_exists, get_table_info
)

# Set page configuration first — must be the very first Streamlit call
st.set_page_config(
    page_title="DC Test Structure Analysis Dashboard",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Try to import modules, with fallback if not available
_MODULE_IMPORT_ERROR = None
try:
    from modules import (
        # DatabaseSummaryModule,
        OxidationAnalysisModule,
        JcDropAirBridgeModule,
        # ManhattanJJResistanceAnalysisModule,
        DolanJJResistanceAnalysisModule,
        JcLinearFittingModule,
        ContactResistanceAnalysisModule,
        M1EtchBiasAnalysisModule,
        SheetResistanceAnalysisModule,
        ElectricalOffsetAnalysisModule,
        DolanJcAnalysisModule,
        EffectiveSingleJJWidthModule,
        JJagingModule,
        FixedFrequencyTransmonModule,
        FixedFrequencyTransmonDeviceModule,
        EJvsJJAreaModule,
        NanoFFWafermapModule,
        ProcessParameterComparisonModule
    )
    MODULES_AVAILABLE = True
except Exception as e:
    MODULES_AVAILABLE = False
    _MODULE_IMPORT_ERROR = traceback.format_exc()

from components.wafer_filter import WaferFilter

class DatabaseManager:
    """Centralized database management class"""
    
    def __init__(self):
        self.db_path = get_database_path()
        self._cached_data = {}
        # shows the database path in the app for debugging
        # st.write(f"Using database at: {self.db_path}")
    
    _EXCLUDE_TABLES_DEFAULT = [
        'Fab_Process_Parameter',
        'MAN1_woABR_woUMP', 'MAN1_wABR_woUMP',
        'DOL1_woABR_woUMP', 'DOL1_wABR_woUMP',
        'DOL2_woABR_woUMP', 'DOL2_wABR_woUMP',
    ]

    @st.cache_data(ttl=300)
    def load_all_analysis_data_full(_self, exclude_tables=None):
        """Load ALL analysis data for every wafer once; filter in memory afterwards.
        The cache key never changes (no wafer list), so subsequent wafer changes are instant."""
        if exclude_tables is None:
            exclude_tables = _self._EXCLUDE_TABLES_DEFAULT

        all_tables = get_table_names()
        analysis_tables = [t for t in all_tables if t not in exclude_tables]

        combined_data = []
        for table in analysis_tables:
            df = load_table_data(table)
            if not df.empty:
                df['Option'] = table
                combined_data.append(df)

        if combined_data:
            return pd.concat(combined_data, ignore_index=True)
        return pd.DataFrame()

    @st.cache_data(ttl=300)
    def load_all_analysis_data(_self, exclude_tables=None, selected_wafers=None):
        """Load and combine all analysis data tables with optional wafer filtering"""
        if exclude_tables is None:
            exclude_tables = _self._EXCLUDE_TABLES_DEFAULT

        all_tables = get_table_names()
        analysis_tables = [t for t in all_tables if t not in exclude_tables]

        combined_data = []
        for table in analysis_tables:
            if selected_wafers:
                df = _self._load_table_with_wafer_filter(table, selected_wafers)
            else:
                df = load_table_data(table)

            if not df.empty:
                df['Option'] = table
                combined_data.append(df)

        if combined_data:
            return pd.concat(combined_data, ignore_index=True)
        return pd.DataFrame()
    
    def _load_table_with_wafer_filter(self, table_name, selected_wafers):
        """Load table data filtered by specific wafers for better performance"""
        try:
            # Check if table exists
            if not check_table_exists(table_name):
                return pd.DataFrame()
            
            # Load full table (we'll implement SQL filtering later for better performance)
            df = load_table_data(table_name)
            
            if df.empty:
                return pd.DataFrame()
            
            # Standardize wafer column name
            wafer_column = None
            if 'Wafer' in df.columns:
                wafer_column = 'Wafer'
            elif 'wafer_name' in df.columns:
                df = df.rename(columns={'wafer_name': 'Wafer'})
                wafer_column = 'Wafer'
            
            # Filter by selected wafers if wafer column exists
            if wafer_column and selected_wafers:
                df = df[df[wafer_column].isin(selected_wafers)]
            
            return df
                
        except Exception as e:
            st.warning(f"Error loading filtered data for table {table_name}: {e}")
            # Fallback to full table load
            return load_table_data(table_name)
    
    @st.cache_data(ttl=300)
    def load_metadata_table(_self, table_name, selected_wafers=None):
        """Load specific metadata tables with optional wafer filtering"""
        if check_table_exists(table_name):
            if selected_wafers:
                return _self._load_table_with_wafer_filter(table_name, selected_wafers)
            else:
                return load_table_data(table_name)
        return pd.DataFrame()
    
    def get_recent_wafers(self, days_back=60):
        """Filter wafers based on Fab_Process_Parameter table processing dates"""
        fab_process_df = self.load_metadata_table('Fab_Process_Parameter')

        if fab_process_df.empty or 'processing_date' not in fab_process_df.columns:
            return None
            
        # Handle date parsing
        def parse_date(date_str):
            if isinstance(date_str, str):
                # Handle list string format like "['2025-06-10']"
                cleaned = date_str.strip("[]").strip().strip("'").strip('"')
                try:
                    return pd.to_datetime(cleaned)
                except:
                    return None
            return pd.to_datetime(date_str, errors='coerce')

        fab_process_df['parsed_date'] = fab_process_df['processing_date'].apply(parse_date)

        # Filter recent wafers
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_wafers = fab_process_df[
            fab_process_df['parsed_date'] >= cutoff_date
        ]
        
        # Get wafer names (handle both column name formats)
        wafer_col = 'Wafer' if 'Wafer' in recent_wafers.columns else 'wafer_name'
        if wafer_col in recent_wafers.columns:
            return recent_wafers[wafer_col].dropna().unique().tolist()
        
        return None

class DataProcessor:
    """Data processing and filtering utilities"""
    
    @staticmethod
    def standardize_wafer_column(df):
        """Ensure consistent Wafer column naming"""
        if 'wafer_name' in df.columns and 'Wafer' not in df.columns:
            df = df.rename(columns={'wafer_name': 'Wafer'})
        elif 'Wafer' not in df.columns:
            df['Wafer'] = 'Unknown'
        return df
    
    @staticmethod
    def filter_by_wafers(df, selected_wafers):
        """Filter dataframe by selected wafers"""
        if not selected_wafers:
            return df
        return df[df['Wafer'].isin(selected_wafers)]
    
    @staticmethod
    def filter_by_options(df, selected_options):
        """Filter dataframe by analysis options"""
        if not selected_options:
            return df
        return df[df['Option'].isin(selected_options)]

def main():
    st.title("🔬 DC Test Structure Analysis Dashboard")
    st.markdown("---")
    
    # Initialize components
    db_manager = DatabaseManager()
    data_processor = DataProcessor()
    
    # Quick reload functionality
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("🔄 Reload Database", key="reload_db"):
            st.cache_data.clear()
            st.success("✅ Database cache cleared!")
            st.rerun()


    # Initialize wafer filter
    wafer_filter = WaferFilter()
    
    # First, get all available wafers from Fab_Process_Parameter for the filter
    with st.sidebar:
        st.subheader("⚡ Data Loading Mode")
        loading_mode = st.radio(
            "Loading strategy:",
            options=["Per selection", "All wafers (faster switching)"],
            index=1,
            key="loading_mode",
            help=(
                "Per selection: queries only selected wafers — lower memory, slower on each change.\n\n"
                "All wafers: loads everything once, then filters in memory — instant wafer switching "
                "after the first load, but uses more RAM."
            ),
        )
        st.markdown("---")

        # Get all available wafers from the metadata table (lightweight query)
        fab_process_df = db_manager.load_metadata_table('Fab_Process_Parameter')
        if not fab_process_df.empty:
            # Standardize wafer column name
            if 'wafer_name' in fab_process_df.columns and 'Wafer' not in fab_process_df.columns:
                fab_process_df = fab_process_df.rename(columns={'wafer_name': 'Wafer'})
            
            all_wafers = sorted([w for w in fab_process_df['Wafer'].unique() if pd.notna(w)])
        else:
            all_wafers = []
            st.warning("⚠️ No wafer metadata found. Loading all data...")
    
    # Render wafer filter in sidebar
    selected_wafers = wafer_filter.render_sidebar_filter(all_wafers)
    
    if not selected_wafers:
        st.warning("⚠️ No wafers selected. Please select wafers in the sidebar.")
        return
    
    # Store the full fab process df in session state for display
    if not fab_process_df.empty:
        st.session_state['fab_process_full_df'] = fab_process_df
    
    # Update the Fab Process Parameter display with filtered wafers
    if 'fab_process_full_df' in st.session_state:
        fab_process_df = st.session_state['fab_process_full_df']
        filtered_fab_df = fab_process_df[fab_process_df['Wafer'].isin(selected_wafers)]
        
        # Display in the expander that was created earlier
        with st.expander("🏭 Fab Process Parameters (Selected Wafers)", expanded=True):
            if not filtered_fab_df.empty:
                # Sort by wafer name for better readability
                filtered_fab_df_display = filtered_fab_df.sort_values('Wafer')
                
                # Display key columns if they exist
                available_display_cols = [col for col in filtered_fab_df_display.columns]
                
                if available_display_cols:
                    st.dataframe(
                        filtered_fab_df_display[available_display_cols],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    # Show all columns if preferred columns aren't available
                    st.dataframe(filtered_fab_df_display, use_container_width=True, hide_index=True)
                
                st.caption(f"Showing {len(filtered_fab_df_display)} wafer(s)")
            else:
                st.info("No Fab Process Parameters found for selected wafers.")
    
    
    # Load analysis data using the strategy chosen in the sidebar
    if loading_mode == "All wafers (faster switching)":
        with st.spinner("Loading full dataset (cached after first load)..."):
            df_full = db_manager.load_all_analysis_data_full()
        df = df_full[df_full['Wafer'].isin(selected_wafers)] if not df_full.empty else pd.DataFrame()
    else:
        with st.spinner(f"Loading data for {len(selected_wafers)} selected wafer(s)..."):
            df = db_manager.load_all_analysis_data(selected_wafers=selected_wafers)
    
    if df.empty:
        st.error("No data found for selected wafers! Please check your database or select different wafers.")
        return

    
    if not MODULES_AVAILABLE:
        st.error("❌ Analysis modules failed to import. See details below.")
        if _MODULE_IMPORT_ERROR:
            st.code(_MODULE_IMPORT_ERROR, language="python")
        return
    
    # Define analysis modules organized by categories
    analysis_categories = {
        "Process Analysis": {
            "Jc vs. Oxidation": OxidationAnalysisModule,
            "JJ Aging": JJagingModule,
            "Contact Resistance": ContactResistanceAnalysisModule,
            "M1 Etch Bias": M1EtchBiasAnalysisModule,
            "Sheet Resistance": SheetResistanceAnalysisModule,
            "Jc drop due to Air Bridges": JcDropAirBridgeModule,
            "JJ Width & Length Process Bias": ElectricalOffsetAnalysisModule,
            "Process Parameter Comparison": ProcessParameterComparisonModule,
        },
        "Device Analysis": {
            "Jc Linear Fitting Viewer": JcLinearFittingModule,
            "Dolan Jc Distribution": DolanJcAnalysisModule,
            "Dolan JJ Resistance vs area": DolanJJResistanceAnalysisModule,
            "Effective Single JJ Width": EffectiveSingleJJWidthModule,
            # "Manhattan JJ Resistance vs area": ManhattanJJResistanceAnalysisModule,
            # "Yield Analysis": YieldAnalysisModule,  # Future: modules/yield_analysis.py
        },
        "Candle Qubit Analysis": {
            "Nano FF Coherence": FixedFrequencyTransmonModule,
            "Nano FF Device": FixedFrequencyTransmonDeviceModule,
            "Nano FF Fudge Factor": EJvsJJAreaModule,
            "Nano FF Wafermap": NanoFFWafermapModule,
        },
        "Database Tools": {
            # "Database Summary": DatabaseSummaryModule,
        }
    }
    
    # Create tabs for each category with state persistence
    category_names = list(analysis_categories.keys())
    if category_names:
        # Filter out categories with no available modules
        available_categories = {cat: modules for cat, modules in analysis_categories.items() if modules}
        
        if available_categories:
            # Initialize session state for active tabs if not exists
            if 'active_category_tab' not in st.session_state:
                st.session_state.active_category_tab = list(available_categories.keys())[0]
            
            if 'active_module_tabs' not in st.session_state:
                st.session_state.active_module_tabs = {}
            
            # Create tab selection using radio buttons for persistence
            st.markdown("### 📑 Analysis Categories")
            selected_category = st.radio(
                "Select Analysis Category:",
                options=list(available_categories.keys()),
                index=list(available_categories.keys()).index(st.session_state.active_category_tab) if st.session_state.active_category_tab in available_categories else 0,
                horizontal=True,
                key="category_selector",
                label_visibility="collapsed"
            )
            
            # Update session state
            st.session_state.active_category_tab = selected_category
            
            st.markdown("---")
            
            # Render the selected category
            category_name = selected_category
            modules = available_categories[category_name]
            
            st.subheader(f"📊 {category_name}")
            
            if len(modules) == 1:
                # If only one module in category, render it directly
                module_name, module_class = next(iter(modules.items()))
                st.markdown(f"**{module_name}**")
                
                # Use unique key prefix for this module
                module_key_prefix = f"{category_name}_{module_name}".replace(" ", "_")
                module = module_class(module_name, db_manager, data_processor, key_prefix=module_key_prefix)
                
                # Pass both df and selected_wafers to the module
                if hasattr(module, 'render'):
                    # Pass selected_wafers as a keyword argument
                    module.render(df, selected_wafers=selected_wafers)
                else:
                    st.error(f"Module {module_name} does not have a render method")
            else:
                # If multiple modules, use radio buttons for sub-module selection
                if category_name not in st.session_state.active_module_tabs:
                    st.session_state.active_module_tabs[category_name] = list(modules.keys())[0]
                
                selected_module = st.radio(
                    "Select Analysis Module:",
                    options=list(modules.keys()),
                    index=list(modules.keys()).index(st.session_state.active_module_tabs[category_name]) if st.session_state.active_module_tabs[category_name] in modules else 0,
                    horizontal=True,
                    key=f"module_selector_{category_name}",
                    label_visibility="collapsed"
                )
                
                # Update session state
                st.session_state.active_module_tabs[category_name] = selected_module
                
                st.markdown("---")
                
                # Render the selected module
                module_name = selected_module
                module_class = modules[module_name]
                
                # Use unique key prefix for this module
                module_key_prefix = f"{category_name}_{module_name}".replace(" ", "_")
                module = module_class(module_name, db_manager, data_processor, key_prefix=module_key_prefix)
                
                # Pass both df and selected_wafers to the module
                if hasattr(module, 'render'):
                    # Pass selected_wafers as a keyword argument
                    module.render(df, selected_wafers=selected_wafers)
                else:
                    st.error(f"Module {module_name} does not have a render method")
        else:
            st.warning("No analysis modules are currently available.")
    else:
        st.warning("No analysis categories defined.")
    


if __name__ == "__main__":
    main()