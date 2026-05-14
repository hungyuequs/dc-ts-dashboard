"""
JJ Aging Analysis Module

This module provides junction aging analysis functionality by tracking
Jc changes over time for selected wafers.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc
from scipy import stats
from datetime import datetime
from .base import AnalysisModule


class JJagingModule(AnalysisModule):
    """JJ aging analysis module - track Jc changes over time"""
    
    def render(self, df, **kwargs):
        st.header("⏰ JJ Aging Analysis")
        
        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)

        # Filter data by junction type categories
        manhattan_options = df[df['Option'].str.contains('Manhattan_JJ', case=False, na=False)]['Option'].unique()
        dolan_options = df[df['Option'].str.contains('Dolan_JJ', case=False, na=False)]['Option'].unique()
        
        # Create category selection
        st.subheader("🔧 Analysis Settings")
        col_cat, col_opt = st.columns([1, 2])
        
        with col_cat:
            jj_category = st.selectbox(
                "Select Junction Type:",
                ['Dolan_JJ', 'Manhattan_JJ'],
                index=0,  # Default to Dolan_JJ
                key=self.get_key('jj_category')
            )
        
        with col_opt:
            # Get available options for selected category
            if jj_category == 'Dolan_JJ':
                available_options = sorted(dolan_options)
                # Default to only Const_W options for Dolan_JJ
                default_options = [opt for opt in available_options if 'Const_W' in opt]
                if not default_options:  # Fallback to all if no Const_W found
                    default_options = available_options
            else:
                available_options = sorted(manhattan_options)
                default_options = available_options
            
            if len(available_options) == 0:
                st.warning(f"No {jj_category} options found in the data.")
                return
            
            selected_options = st.multiselect(
                f"Select {jj_category} Options:",
                available_options,
                default=default_options,
                key=self.get_key('selected_options')
            )
        
        if not selected_options:
            st.warning("Please select at least one option.")
            return
        
        # Filter data by selected options
        df = df[df['Option'].isin(selected_options)]
        
        # Always use Jc_by_die_considering_offset
        jc_type = 'Jc_by_die_considering_offset'

        # Load fabrication process data to get processing dates
        fab_process_df = self.db_manager.load_metadata_table('Fab_Process_Parameter')
        
        if fab_process_df.empty or 'processing_date' not in fab_process_df.columns:
            st.error("❌ Fab Process Parameter table not found or missing 'processing_date' column.")
            st.info("This analysis requires processing date information to track aging.")
            return
        
        # Standardize column names
        if 'wafer_name' in fab_process_df.columns and 'Wafer' not in fab_process_df.columns:
            fab_process_df = fab_process_df.rename(columns={'wafer_name': 'Wafer'})
        
        # Parse processing dates
        def parse_date(date_str):
            if pd.isna(date_str):
                return None
            if isinstance(date_str, str):
                # Handle list string format like "['2025-06-10']"
                cleaned = date_str.strip("[]").strip().strip("'").strip('"')
                try:
                    return pd.to_datetime(cleaned)
                except:
                    return None
            return pd.to_datetime(date_str, errors='coerce')
        
        fab_process_df['parsed_date'] = fab_process_df['processing_date'].apply(parse_date)
        
        # Prepare data for scatter plot
        # Ensure unique Jc values using Die for each wafer
        df = df.drop_duplicates(subset=['Wafer', 'Die', 'Option'])

        # Merge processing date data
        df = df.merge(fab_process_df[['Wafer', 'parsed_date']], on='Wafer', how='left')
        
        # Filter out rows with missing date or Jc data
        df_filtered = df[
            (df['parsed_date'].notna()) & 
            (df[jc_type].notna()) & 
            (df[jc_type] > 0)
        ].copy()
        
        if df_filtered.empty:
            st.warning("⚠️ No valid data found with both processing dates and Jc values.")
            return
        
        # Sort wafers by extracting Day number from wafer name if possible
        def extract_day_number(wafer_name):
            """Extract day number from wafer name like CCE2-Day3_25_1_3 -> 3"""
            import re
            match = re.search(r'Day(\d+)', str(wafer_name), re.IGNORECASE)
            if match:
                return int(match.group(1))
            return 999  # Put wafers without Day number at the end
        
        df_filtered['day_sort_key'] = df_filtered['Wafer'].apply(extract_day_number)
        
        # Filter to only include wafers that have "Day" in their name
        df_filtered = df_filtered[df_filtered['day_sort_key'] != 999].copy()
        
        if df_filtered.empty:
            st.warning("⚠️ No wafers found with 'DayX' pattern in their names (e.g., Day0, Day3, Day6).")
            st.info("Expected wafer naming format: mask-DayX_year_lot_number (e.g., CCE2-Day3_25_1_3)")
            return
        
        df_filtered = df_filtered.sort_values('day_sort_key')
        
        # Extract base wafer name (without DayX)
        def extract_base_wafer_name(wafer_name):
            """Extract base wafer name by removing DayX_ pattern (e.g., CCE2-Day3_25_1_3 -> CCE2_25_1_3)"""
            import re
            # Remove -DayX_ pattern
            cleaned = re.sub(r'-Day\d+_', '_', str(wafer_name))
            return cleaned
        
        df_filtered['base_wafer'] = df_filtered['Wafer'].apply(extract_base_wafer_name)
        
        # Get unique base wafer names
        unique_base_wafers = sorted(df_filtered['base_wafer'].unique())
        
        # Wafer selection
        st.subheader("🔧 Wafer Selection")
        selected_base_wafers = st.multiselect(
            "Select wafers to plot (by base name):",
            unique_base_wafers,
            default=unique_base_wafers,
            key=self.get_key('selected_base_wafers')
        )
        
        if not selected_base_wafers:
            st.warning("Please select at least one wafer to plot.")
            return
        
        # Filter by selected base wafers
        df_filtered = df_filtered[df_filtered['base_wafer'].isin(selected_base_wafers)].copy()

        # PLOT: Jc_by_die_considering_offset vs Day Number
        st.subheader("📊 Jc (Considering Offset) vs Day Number")
        st.write(f"Data points from {df_filtered['Wafer'].nunique()} unique wafers and {df_filtered['Die'].nunique()} unique dies.")
        st.info("X-axis shows day number extracted from wafer name (e.g., Day0, Day3, Day6)")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            color_by = st.selectbox("Color points by:", ['Option', 'Wafer', 'Die', 'Base Wafer'], index=3, key=self.get_key("color_by"))
        with col2:
            marker_by = st.selectbox("Marker type by:", ['Option', 'Wafer', 'Die', 'Base Wafer'], index=2, key=self.get_key("marker_by"))
        with col3:
            log_scale_y = st.checkbox("Log scale Y-axis", value=False, key=self.get_key("log_y"))
        with col4:
            show_day_avg = st.checkbox("Show avg per day", value=True, key=self.get_key("show_day_avg"), help="Show average Jc per day with error bars (±1 std)")

        # Create plot
        fig = go.Figure()
        
        # Define marker symbols for different categories
        marker_symbols = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'triangle-down', 'pentagon', 'hexagon', 'star']
        
        # Map 'Base Wafer' selection to actual column name
        color_col = 'base_wafer' if color_by == 'Base Wafer' else color_by
        marker_col = 'base_wafer' if marker_by == 'Base Wafer' else marker_by
        
        # Get unique values for color and marker assignments
        color_values = sorted([v for v in df_filtered[color_col].unique() if pd.notna(v)])
        marker_values = sorted([v for v in df_filtered[marker_col].unique() if pd.notna(v)])
        
        # Create color map using plotly default colors
        colors = pc.qualitative.Plotly + pc.qualitative.Set1 + pc.qualitative.Set2
        color_map = {val: colors[i % len(colors)] for i, val in enumerate(color_values)}
        marker_map = {val: marker_symbols[i % len(marker_symbols)] for i, val in enumerate(marker_values)}
        
        # If color_by and marker_by are the same, use single trace per value
        if color_col == marker_col:
            for value in color_values:
                filtered_data = df_filtered[df_filtered[color_col] == value]
                marker_symbol = marker_map.get(value, 'circle')
                assigned_color = color_map.get(value)
                
                y_data = np.log10(filtered_data[jc_type]) if log_scale_y else filtered_data[jc_type]
                
                fig.add_trace(go.Scatter(
                    x=filtered_data['day_sort_key'],
                    y=y_data,
                    mode='markers',
                    name=f"{value}",
                    marker=dict(symbol=marker_symbol, size=10, color=assigned_color),
                    text=filtered_data['Wafer'] + ', Die: ' + filtered_data['Die'].astype(str) + ', Option: ' + filtered_data['Option'] + ', Base: ' + filtered_data['base_wafer'],
                    customdata=np.column_stack([
                        filtered_data['Wafer'],
                        filtered_data['day_sort_key'],
                        filtered_data[jc_type],
                        filtered_data['parsed_date'].dt.strftime('%Y-%m-%d')
                    ]),
                    hovertemplate='%{text}<br>Day: %{customdata[1]:.0f}<br>Jc: %{customdata[2]:.3f} µA/µm²<br>Processed: %{customdata[3]}<extra></extra>'
                ))
        else:
            # Group by both color and marker categories
            for color_value in color_values:
                color_filtered = df_filtered[df_filtered[color_col] == color_value]
                assigned_color = color_map.get(color_value)
                
                for marker_value in marker_values:
                    marker_filtered = color_filtered[color_filtered[marker_col] == marker_value]
                    if not marker_filtered.empty:
                        marker_symbol = marker_map.get(marker_value, 'circle')
                        legend_name = f"{color_value} ({marker_by}: {marker_value})"
                        
                        y_data = np.log10(marker_filtered[jc_type]) if log_scale_y else marker_filtered[jc_type]
                        
                        fig.add_trace(go.Scatter(
                            x=marker_filtered['day_sort_key'],
                            y=y_data,
                            mode='markers',
                            name=legend_name,
                            marker=dict(symbol=marker_symbol, size=10, color=assigned_color),
                            text=marker_filtered['Wafer'] + ', Die: ' + marker_filtered['Die'].astype(str) + ', Option: ' + marker_filtered['Option'] + ', Base: ' + marker_filtered['base_wafer'],
                            customdata=np.column_stack([
                                marker_filtered['Wafer'],
                                marker_filtered['day_sort_key'],
                                marker_filtered[jc_type],
                                marker_filtered['parsed_date'].dt.strftime('%Y-%m-%d')
                            ]),
                            hovertemplate='%{text}<br>Day: %{customdata[1]:.0f}<br>Jc: %{customdata[2]:.3f} µA/µm²<br>Processed: %{customdata[3]}<extra></extra>'
                        ))

        # Add average Jc per day if requested
        if show_day_avg:
            # Calculate average and std for each day
            day_stats = df_filtered.groupby('day_sort_key')[jc_type].agg(['mean', 'std', 'count']).reset_index()
            day_stats = day_stats.sort_values('day_sort_key')
            
            # Prepare data for plotting
            avg_y_data = np.log10(day_stats['mean']) if log_scale_y else day_stats['mean']
            
            # Calculate error bars (std)
            if log_scale_y:
                # For log scale, calculate error in log space
                # std in log space = log10(value + std) - log10(value)
                error_y_upper = np.log10(day_stats['mean'] + day_stats['std']) - np.log10(day_stats['mean'])
                error_y_lower = np.log10(day_stats['mean']) - np.log10(day_stats['mean'] - day_stats['std'])
                # Handle cases where mean - std might be negative or zero
                error_y_lower = np.where(day_stats['mean'] > day_stats['std'], error_y_lower, avg_y_data)
                error_bar = dict(
                    type='data',
                    symmetric=False,
                    array=error_y_upper,
                    arrayminus=error_y_lower,
                    visible=True,
                    color='black',
                    thickness=3,
                    width=8
                )
            else:
                # For linear scale, use std directly
                error_bar = dict(
                    type='data',
                    array=day_stats['std'],
                    visible=True,
                    color='black',
                    thickness=3,
                    width=8
                )
            
            # Add average trace
            fig.add_trace(go.Scatter(
                x=day_stats['day_sort_key'],
                y=avg_y_data,
                mode='markers+lines',
                name='Average per Day',
                marker=dict(
                    size=14,
                    color='black',
                    symbol='diamond',
                    line=dict(width=2, color='white')
                ),
                line=dict(color='black', width=3, dash='solid'),
                error_y=error_bar,
                customdata=np.column_stack([
                    day_stats['day_sort_key'],
                    day_stats['mean'],
                    day_stats['std'],
                    day_stats['count']
                ]),
                hovertemplate='<b>Day %{customdata[0]:.0f} Average</b><br>Mean Jc: %{customdata[1]:.3f} µA/µm²<br>Std Dev: %{customdata[2]:.3f} µA/µm²<br>N: %{customdata[3]:.0f}<extra></extra>',
                showlegend=True
            ))

        y_axis_title = "log₁₀(Jc Considering Offset [µA/µm²])" if log_scale_y else "Jc Considering Offset (µA/µm²)"
        
        fig.update_layout(
            title=f"JJ Aging: Jc vs Day Number - {jj_category}",
            xaxis_title="Day Number",
            yaxis_title=y_axis_title,
            showlegend=True,
            height=600,
            hovermode='closest'
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # Display data summary table
        st.markdown("---")
        st.subheader("📋 Data Summary")
        
        summary_data = df_filtered.groupby('Wafer').agg({
            jc_type: ['mean', 'std', 'min', 'max', 'count'],
            'day_sort_key': 'first',
            'parsed_date': 'first'
        }).reset_index()
        
        summary_data.columns = ['Wafer', 'Jc Mean (µA/µm²)', 'Jc Std', 'Jc Min', 'Jc Max', 'Count', 'Day Number', 'Processing Date']
        summary_data['Processing Date'] = pd.to_datetime(summary_data['Processing Date']).dt.strftime('%Y-%m-%d')
        summary_data = summary_data.sort_values('Day Number')
        
        st.dataframe(summary_data, use_container_width=True, hide_index=True)
        
        # Export data
        st.markdown("---")
        st.subheader("💾 Export Data")
        
        export_df = df_filtered[['Wafer', 'Die', 'Option', jc_type, 'day_sort_key', 'parsed_date']].copy()
        export_df['parsed_date'] = export_df['parsed_date'].dt.strftime('%Y-%m-%d')
        export_df = export_df.rename(columns={
            jc_type: 'Jc_considering_offset',
            'day_sort_key': 'Day_Number',
            'parsed_date': 'Processing_Date'
        })
        
        csv = export_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"jj_aging_analysis_{jj_category}.csv",
            mime="text/csv",
            key=self.get_key('download')
        )
        
        st.caption(f"Export includes {len(export_df)} data points")
