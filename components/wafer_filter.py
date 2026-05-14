"""
Advanced Wafer Filtering Component
Uses JJ_Process table to filter wafers by processing date for better performance
"""

import streamlit as st
import pandas as pd
import sys
import os
import re
from datetime import datetime, timedelta
from components.database_utility import (
    ensure_database_exists, append_data_to_table, get_database_path,
    get_table_names, load_table_data, check_table_exists, get_table_info,
    get_column_names, filter_table_data
)

class WaferFilter:
    """Advanced wafer filtering component using Fab_Process_Parameter data"""
    
    def __init__(self):
        self.fab_process_table = 'Fab_Process_Parameter'
        self._cached_fab_data = None
        self.default_filter_columns = ["wafer_vendor", "IM time (sec)", "BOE time (sec)"]

    def get_available_filter_columns(self):
        """Get available columns from Fab_Process_Parameter table that can be used for filtering"""
        if not check_table_exists(self.fab_process_table):
            return []
        
        all_columns = get_column_names(self.fab_process_table)
        
        # Filter out columns that are not suitable for filtering
        exclude_columns = ['Wafer', 'wafer_name', 'processing_date', 'parsed_date']
        filter_columns = [col for col in all_columns if col not in exclude_columns]
        
        return filter_columns
    
    def get_default_filter_columns(self):
        """Get default filterable columns, fallback to available if defaults don't exist"""
        available_columns = self.get_available_filter_columns()
        
        # Check which default columns actually exist in the table
        existing_defaults = [col for col in self.default_filter_columns if col in available_columns]
        
        # If none of the defaults exist, return first few available columns
        if not existing_defaults and available_columns:
            return available_columns[:3]  # Return first 3 columns as fallback
        
        return existing_defaults
    
    def get_unique_column_values(self, column_name):
        """Get unique values for a specific column in Fab_Process_Parameter table"""
        if not check_table_exists(self.fab_process_table):
            return []
        
        fab_data = self._load_fab_process_data()
        if fab_data.empty or column_name not in fab_data.columns:
            return []
        
        # Get unique values, excluding None/NaN
        unique_values = fab_data[column_name].dropna().unique().tolist()
        
        # Sort values if they are strings or numbers
        try:
            unique_values.sort()
        except:
            pass  # If sorting fails, return unsorted
        
        return unique_values
    
    def is_numeric_column(self, column_name):
        """Check if a column contains numeric values suitable for slider filtering"""
        if not check_table_exists(self.fab_process_table):
            return False
        
        fab_data = self._load_fab_process_data()
        if fab_data.empty or column_name not in fab_data.columns:
            return False
        
        # Get non-null values
        values = fab_data[column_name].dropna()
        if values.empty:
            return False
        
        # Try to convert to numeric
        try:
            numeric_values = pd.to_numeric(values, errors='coerce')
            # Consider it numeric if at least 80% of values are numeric
            numeric_ratio = numeric_values.notna().sum() / len(values)
            return numeric_ratio >= 0.8
        except:
            return False
    
    def get_column_range(self, column_name):
        """Get min and max values for a numeric column"""
        if not check_table_exists(self.fab_process_table):
            return None, None
        
        fab_data = self._load_fab_process_data()
        if fab_data.empty or column_name not in fab_data.columns:
            return None, None
        
        # Convert to numeric and get range
        try:
            numeric_values = pd.to_numeric(fab_data[column_name], errors='coerce').dropna()
            if numeric_values.empty:
                return None, None
            return float(numeric_values.min()), float(numeric_values.max())
        except:
            return None, None
    
    def _parse_wafer_names(self, wafer_names):
        """Parse wafer names into components: mask-XXX_year_lot_number
        
        Args:
            wafer_names (list): List of wafer names to parse
            
        Returns:
            dict: {wafer_name: {'mask': str, 'type': str, 'day': int or None, 'process': list, 'year': str, 'lot': str, 'number': str}}
        """
        import re
        
        parsed = {}
        # Pattern: mask-XXX_year_lot_number or mask_year_lot_number (no XXX)
        # XXX can be Day5, ABR, STRAP, Day5-ABR, etc.
        pattern = r'^([^-_]+)(?:-([^_]+))?_([^_]+)_([^_]+)_([^_]+)$'
        
        for wafer in wafer_names:
            match = re.match(pattern, wafer)
            if match:
                mask, type_suffix, year, lot, number = match.groups()
                
                # Parse type_suffix into day number and process types
                day_number = None
                process_types = []
                
                if type_suffix:
                    # Extract day number (e.g., Day5 -> 5)
                    day_match = re.search(r'Day(\d+)', type_suffix)
                    if day_match:
                        day_number = int(day_match.group(1))
                    
                    # Extract process types (ABR, STRAP, etc.)
                    # Split by dash and filter out Day components
                    parts = type_suffix.split('-')
                    for part in parts:
                        if part and not part.startswith('Day'):
                            process_types.append(part)
                
                parsed[wafer] = {
                    'mask': mask,
                    'type': type_suffix if type_suffix else '',  # Keep original for reference
                    'day': day_number,  # None if no day, otherwise int
                    'process': process_types,  # List of process types like ['ABR'], ['STRAP'], ['ABR', 'STRAP'], or []
                    'year': year,
                    'lot': lot,
                    'number': number
                }
        
        return parsed
    
    def filter_wafers_by_columns(self, selected_wafers, column_filters):
        """
        Filter wafers based on column values from Fab_Process_Parameter table
        
        Args:
            selected_wafers (list): List of wafers to filter
            column_filters (dict): Dictionary of {column_name: filter_criteria} pairs
                                 For numeric columns: {'min': min_val, 'max': max_val}
                                 For categorical columns: [selected_values]
            
        Returns:
            list: Filtered list of wafers
        """
        if not column_filters or not selected_wafers:
            return selected_wafers
        
        fab_data = self._load_fab_process_data()
        if fab_data.empty:
            return selected_wafers
        
        # Start with all wafers
        filtered_data = fab_data.copy()
        
        # Apply each column filter
        for column_name, filter_criteria in column_filters.items():
            if column_name not in filtered_data.columns:
                continue
                
            if isinstance(filter_criteria, dict) and 'min' in filter_criteria and 'max' in filter_criteria:
                # Numeric range filtering
                min_val = filter_criteria['min']
                max_val = filter_criteria['max']
                
                # Convert column to numeric for filtering
                numeric_col = pd.to_numeric(filtered_data[column_name], errors='coerce')
                filtered_data = filtered_data[
                    (numeric_col >= min_val) & (numeric_col <= max_val)
                ]
            elif isinstance(filter_criteria, list) and filter_criteria:
                # Categorical value filtering
                filtered_data = filtered_data[filtered_data[column_name].isin(filter_criteria)]
        
        # Get wafers that meet all filter criteria
        filtered_wafers = filtered_data['Wafer'].dropna().unique().tolist()
        
        # Return intersection of filtered wafers and originally selected wafers
        return [w for w in selected_wafers if w in filtered_wafers]

    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def _load_fab_process_data(_self):
        """Load JJ Process data with caching"""
        if not check_table_exists(_self.fab_process_table):
            return pd.DataFrame()
        
        df = load_table_data(_self.fab_process_table)

        if df.empty:
            return pd.DataFrame()
        
        # Standardize wafer column name
        if 'wafer_name' in df.columns and 'Wafer' not in df.columns:
            df = df.rename(columns={'wafer_name': 'Wafer'})
        elif 'Wafer' not in df.columns:
            df['Wafer'] = 'Unknown'
        
        return df
    
    def _parse_processing_date(self, date_str):
        """Parse processing date from various formats"""
        if pd.isna(date_str):
            return None
            
        if isinstance(date_str, str):
            # Handle list string format like "['2025-06-10']"
            cleaned = date_str.strip("[]").strip().strip("'").strip('"')
            try:
                return pd.to_datetime(cleaned, errors='coerce')
            except:
                return None
        
        return pd.to_datetime(date_str, errors='coerce')
    
    def get_wafers_by_date_range(self, days_back=60, start_date=None, end_date=None):
        """
        Get wafers processed within a date range
        
        Args:
            days_back (int): Number of days back from today (used if start_date/end_date not provided)
            start_date (datetime): Start date for filtering
            end_date (datetime): End date for filtering
            
        Returns:
            tuple: (filtered_wafers_list, fab_process_filtered_df)
        """
        fab_data = self._load_fab_process_data()

        if fab_data.empty or 'processing_date' not in fab_data.columns:
            return [], pd.DataFrame()
        
        # Parse processing dates
        fab_data['parsed_date'] = fab_data['processing_date'].apply(self._parse_processing_date)
        
        # Remove rows with invalid dates
        fab_data_valid = fab_data.dropna(subset=['parsed_date'])
        
        if fab_data_valid.empty:
            return [], pd.DataFrame()
        
        # Determine date range
        if start_date is None or end_date is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
        
        # Filter by date range
        filtered_data = fab_data_valid[
            (fab_data_valid['parsed_date'] >= start_date) & 
            (fab_data_valid['parsed_date'] <= end_date)
        ]
        
        # Get unique wafer names
        wafers = filtered_data['Wafer'].dropna().unique().tolist()
        
        return wafers, filtered_data
    
    def get_all_wafers_with_dates(self):
        """Get all wafers with their processing dates"""
        fab_data = self._load_fab_process_data()

        if fab_data.empty:
            return pd.DataFrame()
        
        if 'processing_date' not in fab_data.columns:
            return pd.DataFrame()
        
        # Parse dates and create summary
        fab_data['parsed_date'] = fab_data['processing_date'].apply(self._parse_processing_date)

        summary = fab_data.groupby('Wafer').agg({
            'parsed_date': ['min', 'max', 'count']
        }).reset_index()
        
        summary.columns = ['Wafer', 'First_Process_Date', 'Last_Process_Date', 'Process_Count']
        
        return summary.sort_values('Last_Process_Date', ascending=False)
    
    def render_sidebar_filter(self, all_available_wafers):
        """
        Render wafer filtering UI in sidebar
        
        Args:
            all_available_wafers (list): All wafers available in the main dataset
            
        Returns:
            list: Selected wafers after filtering
        """
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Wafer Filtering")

        # Check if Fab Process data is available
        fab_data = self._load_fab_process_data()
        has_fab_data = not fab_data.empty and 'processing_date' in fab_data.columns

        if not has_fab_data:
            st.sidebar.warning("⚠️ No Fab Process date data found")
            st.sidebar.info("Using manual wafer selection only")
            
            # Fallback to manual selection
            selected_wafers = st.sidebar.multiselect(
                "Select Wafers:",
                all_available_wafers,
                default=all_available_wafers[:20] if len(all_available_wafers) > 20 else all_available_wafers,
                help="Manual wafer selection (JJ Process filtering unavailable)"
            )
            
            return selected_wafers
        
        # JJ Process data is available - use date-based filtering
        st.sidebar.markdown("**📅 Date-Based Filtering**")
        days_back = st.sidebar.slider(
            "Show wafers from last N days:",
            min_value=7, max_value=365, value=60, step=7,
            help="Filter wafers based on JJ processing date"
        )
        
        recent_wafers, recent_jj_data = self.get_wafers_by_date_range(days_back=days_back)
        
        # Filter to only wafers that exist in main dataset
        available_recent_wafers = [w for w in recent_wafers if w in all_available_wafers]
        
        st.sidebar.success(f"📅 Found {len(available_recent_wafers)} recent wafers")
        
        # Show processing date summary
        if not recent_jj_data.empty:
            with st.sidebar.expander("📊 Recent Processing Summary"):
                date_range = recent_jj_data['parsed_date']
                st.write(f"**Date Range:** {date_range.min().strftime('%Y-%m-%d')} to {date_range.max().strftime('%Y-%m-%d')}")
                st.write(f"**Total Records:** {len(recent_jj_data)}")
                st.write(f"**Unique Wafers:** {recent_jj_data['Wafer'].nunique()}")
        
        if not available_recent_wafers:
            st.sidebar.error("❌ No recent wafers found in main dataset")
            return []
        
        # STAGE: MASK FILTERING
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎭 Mask Filtering")
        st.sidebar.info("Build wafer collection by selecting mask components")
        
        # Parse wafer names to extract components
        wafer_components = self._parse_wafer_names(available_recent_wafers)
        
        if not wafer_components:
            st.sidebar.warning("⚠️ Could not parse wafer naming convention")
            selected_wafers = available_recent_wafers
        else:
            # Initialize session state for wafer collection
            if 'wafer_collection' not in st.session_state:
                st.session_state['wafer_collection'] = []
            
            # Hierarchical/cascading selectors
            # Level 1: Mask
            all_masks = sorted(set(comp['mask'] for comp in wafer_components.values()))
            
            col1, col2 = st.sidebar.columns(2)
            with col1:
                selected_mask = st.selectbox(
                    "Mask:",
                    all_masks,
                    key="mask_filter_mask",
                    help="Select mask name"
                )
            
            # Level 2: Year (filtered by selected mask)
            available_years = sorted(set(
                comp['year'] for comp in wafer_components.values() 
                if comp['mask'] == selected_mask
            ))
            
            with col2:
                selected_year = st.selectbox(
                    "Year:",
                    available_years,
                    key="mask_filter_year",
                    help="Select year (filtered by mask)"
                )
            
            # Level 3: Lot (filtered by selected mask + year)
            available_lots = sorted(set(
                comp['lot'] for comp in wafer_components.values()
                if comp['mask'] == selected_mask and comp['year'] == selected_year
            ))
            
            col3, col4 = st.sidebar.columns(2)
            with col3:
                selected_lot = st.selectbox(
                    "Lot:",
                    available_lots,
                    key="mask_filter_lot",
                    help="Select lot number (filtered by mask + year)"
                )
            
            # Level 4: Number (filtered by selected mask + year + lot)
            available_numbers = sorted(set(
                comp['number'] for comp in wafer_components.values()
                if comp['mask'] == selected_mask and comp['year'] == selected_year and comp['lot'] == selected_lot
            ))
            
            with col4:
                selected_number = st.selectbox(
                    "Number:",
                    available_numbers,
                    key="mask_filter_number",
                    help="Select wafer number (filtered by mask + year + lot)"
                )
            
            # Day and Process Type selectors (filtered by all selections above)
            available_for_selection = [
                comp for comp in wafer_components.values()
                if comp['mask'] == selected_mask and comp['year'] == selected_year 
                and comp['lot'] == selected_lot and comp['number'] == selected_number
            ]
            
            unique_days = sorted(set(comp['day'] for comp in available_for_selection if comp['day'] is not None))
            unique_processes = sorted(set(p for comp in available_for_selection for p in comp['process']))
            
            st.sidebar.markdown("**Optional Filters:**")
            col5, col6 = st.sidebar.columns(2)
            with col5:
                day_options = ['Any'] + [f"Day {d}" for d in unique_days] + (['No Day'] if any(c['day'] is None for c in available_for_selection) else [])
                selected_day_option = st.selectbox(
                    "Day:",
                    day_options,
                    key="mask_filter_day",
                    help="Filter by probing day. 'Any' = any day or no day, 'No Day' = only wafers without day number"
                )
            
            with col6:
                process_options = ['Any'] + unique_processes + (['None'] if any(len(c['process']) == 0 for c in available_for_selection) else [])
                selected_process_option = st.selectbox(
                    "Process:",
                    process_options,
                    key="mask_filter_process",
                    help="Filter by process type (ABR/STRAP/etc). 'Any' = any process or no process, 'None' = only wafers without process"
                )
            
            # Convert selections to filter criteria
            selected_day = None
            if selected_day_option.startswith('Day '):
                selected_day = int(selected_day_option.split()[1])
            
            selected_process = None
            if selected_process_option not in ['Any', 'None']:
                selected_process = selected_process_option
            
            # Find matching wafers
            matching_wafers = []
            for wafer_name, comp in wafer_components.items():
                # Check basic components
                if not (comp['mask'] == selected_mask and 
                        comp['year'] == selected_year and 
                        comp['lot'] == selected_lot and 
                        comp['number'] == selected_number):
                    continue
                
                # Check day filter
                day_match = False
                if selected_day_option == 'Any':
                    day_match = True
                elif selected_day_option == 'No Day':
                    day_match = (comp['day'] is None)
                elif selected_day is not None:
                    day_match = (comp['day'] == selected_day)
                
                if not day_match:
                    continue
                
                # Check process filter
                process_match = False
                if selected_process_option == 'Any':
                    process_match = True
                elif selected_process_option == 'None':
                    process_match = (len(comp['process']) == 0)
                elif selected_process is not None:
                    process_match = (selected_process in comp['process'])
                
                if process_match:
                    matching_wafers.append(wafer_name)
            
            # Display matching wafers
            if matching_wafers:
                st.sidebar.success(f"✅ {len(matching_wafers)} matching wafer(s) found")
                with st.sidebar.expander("📋 Matching Wafers"):
                    for w in matching_wafers:
                        st.write(f"• {w}")
                
                # Add to collection button
                col_btn1, col_btn2 = st.sidebar.columns(2)
                with col_btn1:
                    if st.button("➕ Add to Collection", key="add_to_collection"):
                        for w in matching_wafers:
                            if w not in st.session_state['wafer_collection']:
                                st.session_state['wafer_collection'].append(w)
                        st.rerun()
                
                with col_btn2:
                    if st.button("🗑️ Clear Collection", key="clear_collection"):
                        st.session_state['wafer_collection'] = []
                        st.rerun()
            else:
                st.sidebar.info("ℹ️ No wafers match current selection")
            
            # Show current collection
            if st.session_state['wafer_collection']:
                st.sidebar.markdown("**📦 Current Collection:**")
                st.sidebar.success(f"{len(st.session_state['wafer_collection'])} wafer(s) in collection")
                
                with st.sidebar.expander("View Collection", expanded=False):
                    for i, w in enumerate(st.session_state['wafer_collection'], 1):
                        col_w, col_x = st.columns([4, 1])
                        with col_w:
                            st.write(f"{i}. {w}")
                        with col_x:
                            if st.button("❌", key=f"remove_{i}"):
                                st.session_state['wafer_collection'].remove(w)
                                st.rerun()
                
                selected_wafers = st.session_state['wafer_collection']
            else:
                st.sidebar.warning("⚠️ No wafers in collection. Add wafers using the controls above.")
                selected_wafers = []
        
        # Additional Fab Process Parameter filtering
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔧 Process Parameter Filtering")
        
        # Get available filter columns
        available_filter_columns = self.get_available_filter_columns()
        default_filter_columns = self.get_default_filter_columns()
        
        if available_filter_columns:
            # Allow user to select which columns to filter by
            filter_columns_to_use = st.sidebar.multiselect(
                "Select columns to filter by:",
                available_filter_columns,
                default=default_filter_columns,
                help="Choose which Fab Process Parameter columns to use for filtering"
            )
            
            column_filters = {}
            if filter_columns_to_use:
                st.sidebar.markdown("**Set filter values for selected columns:**")
                
                for column_name in filter_columns_to_use:
                    # Check if column is numeric
                    if self.is_numeric_column(column_name):
                        # Use sliders for numeric columns
                        min_val, max_val = self.get_column_range(column_name)
                        
                        if min_val is not None and max_val is not None:
                            # Create slider for min/max threshold
                            st.sidebar.markdown(f"**{column_name}** (Range: {min_val:.2f} - {max_val:.2f})")
                            
                            col1, col2 = st.sidebar.columns(2)
                            with col1:
                                filter_min = st.slider(
                                    f"Min {column_name}:",
                                    min_value=min_val,
                                    max_value=max_val,
                                    value=min_val,
                                    step=(max_val - min_val) / 100 if max_val != min_val else 0.1,
                                    help=f"Minimum threshold for {column_name}"
                                )
                            with col2:
                                filter_max = st.slider(
                                    f"Max {column_name}:",
                                    min_value=min_val,
                                    max_value=max_val,
                                    value=max_val,
                                    step=(max_val - min_val) / 100 if max_val != min_val else 0.1,
                                    help=f"Maximum threshold for {column_name}"
                                )
                            
                            # Ensure min <= max
                            if filter_min <= filter_max:
                                column_filters[column_name] = {'min': filter_min, 'max': filter_max}
                            else:
                                st.sidebar.error(f"Min value must be ≤ Max value for {column_name}")
                    else:
                        # Use multiselect for categorical columns
                        unique_values = self.get_unique_column_values(column_name)
                        
                        if unique_values:
                            selected_values = st.sidebar.multiselect(
                                f"{column_name}:",
                                unique_values,
                                default=unique_values,  # Default to all values
                                help=f"Filter wafers by {column_name} values"
                            )
                            
                            if selected_values:
                                column_filters[column_name] = selected_values
                
                # Apply column-based filtering
                if column_filters:
                    pre_filter_count = len(selected_wafers)
                    selected_wafers = self.filter_wafers_by_columns(selected_wafers, column_filters)
                    
                    if len(selected_wafers) < pre_filter_count:
                        st.sidebar.info(f"🔧 Column filters reduced wafers from {pre_filter_count} to {len(selected_wafers)}")
                        
                    # Show active filters
                    with st.sidebar.expander("📋 Active Column Filters"):
                        for col, filter_criteria in column_filters.items():
                            if isinstance(filter_criteria, dict) and 'min' in filter_criteria:
                                # Numeric range filter
                                st.write(f"**{col}:** {filter_criteria['min']:.2f} - {filter_criteria['max']:.2f}")
                            elif isinstance(filter_criteria, list):
                                # Categorical filter
                                st.write(f"**{col}:** {', '.join(map(str, filter_criteria[:3]))}{' ...' if len(filter_criteria) > 3 else ''}")
        else:
            st.sidebar.info("ℹ️ No additional filter columns available in Fab Process Parameter table")

        # Create additional filtering from the selected wafers
        # Create multi-select for any remaining wafers
        if selected_wafers:
            st.sidebar.markdown("---")
            st.sidebar.subheader("📋 Final Wafer Selection")
            
            # Sort wafers alphabetically for display
            sorted_selected_wafers = sorted(selected_wafers)
            
            final_selected_wafers = st.sidebar.multiselect(
                "Refine final wafer selection:",
                sorted_selected_wafers,
                default=sorted_selected_wafers,
                help="Manually refine the final list of selected wafers"
            )
            
            selected_wafers = final_selected_wafers
        # show the count of selected wafers
        st.sidebar.markdown(f"### ✅ {len(selected_wafers)} wafers selected")
        
        return selected_wafers
    
    def show_wafer_summary_table(self):
        """Show a summary table of all wafers with processing dates"""
        st.subheader("📋 Wafer Processing Summary")
        
        summary_df = self.get_all_wafers_with_dates()
        
        if summary_df.empty:
            st.warning("No JJ Process data with dates available")
            return
        
        # Format dates for display
        summary_display = summary_df.copy()
        for date_col in ['First_Process_Date', 'Last_Process_Date']:
            if date_col in summary_display.columns:
                summary_display[date_col] = summary_display[date_col].dt.strftime('%Y-%m-%d')
        
        st.dataframe(summary_display, use_container_width=True)
        st.caption(f"📊 Showing {len(summary_display)} wafers with processing dates")


# Utility function for backward compatibility
def create_wafer_filter():
    """Factory function to create WaferFilter instance"""
    return WaferFilter()
