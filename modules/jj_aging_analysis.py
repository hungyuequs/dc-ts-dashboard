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
from plotly.subplots import make_subplots
from scipy import stats
from datetime import datetime
from .base import AnalysisModule


class JJagingModule(AnalysisModule):
    """JJ aging analysis module - track Jc changes over time"""
    
    def render(self, df, **kwargs):
        st.header("⏰ JJ Aging Analysis")

        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)

        # Keep full copy for section 2 (Resistance) before any filtering
        df_all = df.copy()
        colors = pc.qualitative.Plotly + pc.qualitative.Set1 + pc.qualitative.Set2

        def extract_day_number(wafer_name):
            import re
            match = re.search(r'Day(\d+)', str(wafer_name), re.IGNORECASE)
            return int(match.group(1)) if match else 999

        def extract_base_wafer_name(wafer_name):
            import re
            return re.sub(r'-Day\d+_', '_', str(wafer_name))

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
        
        # Sort wafers by day number extracted from wafer name (function defined above)
        df_filtered['day_sort_key'] = df_filtered['Wafer'].apply(extract_day_number)
        
        # Filter to only include wafers that have "Day" in their name
        df_filtered = df_filtered[df_filtered['day_sort_key'] != 999].copy()
        
        if df_filtered.empty:
            st.warning("⚠️ No wafers found with 'DayX' pattern in their names (e.g., Day0, Day3, Day6).")
            st.info("Expected wafer naming format: mask-DayX_year_lot_number (e.g., CCE2-Day3_25_1_3)")
            return
        
        df_filtered = df_filtered.sort_values('day_sort_key')
        
        # Extract base wafer name without DayX (function defined above)
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

        # ============================================================
        # SECTION 2: Resistance vs Day Number
        # ============================================================
        st.markdown("---")
        st.header("⚡ Resistance vs Day Number (Dolan JJ)")

        dolan_resist_tables = sorted(
            df_all[df_all['Option'].str.contains('Dolan', case=False, na=False)]['Option'].unique()
        )

        if not dolan_resist_tables:
            st.warning("No Dolan JJ tables found in the selected wafer data.")
            return

        st.subheader("🔧 Resistance Analysis Settings")

        # Step 1 — table selection
        selected_resist_tables = st.multiselect(
            "Select Dolan table(s):",
            dolan_resist_tables,
            default=[t for t in dolan_resist_tables if 'Const_W' in t] or dolan_resist_tables,
            key=self.get_key('resist_tables'),
            help="Dolan_Const_W tables fix JJ width; Dolan_Const_L tables fix JJ length."
        )

        if not selected_resist_tables:
            st.info("Select at least one Dolan table above to continue.")
            return

        resist_df = df_all[df_all['Option'].isin(selected_resist_tables)].copy()

        required_cols = ['Resistance', 'alt', 'dia', 'DMM error', 'Contact', 'TS']
        missing_cols = [c for c in required_cols if c not in resist_df.columns]
        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
            return

        # Quality filter — same criteria as DolanJJResistanceAnalysisModule
        resist_df = resist_df[
            resist_df['Resistance'].notna() &
            (resist_df['Resistance'] > 0) &
            (resist_df['DMM error'] == 0) &
            (resist_df['Contact'] == '[1, 1]')
        ].drop_duplicates(subset=['TS', 'Die', 'Wafer'])

        if resist_df.empty:
            st.warning("No valid resistance data after quality filtering.")
            return

        # Step 2 — JJ geometry selection
        available_alts = sorted(resist_df['alt'].dropna().unique().tolist())
        if len(available_alts) >= 2:
            alt_range = st.select_slider(
                "JJ length — alt (µm):",
                options=available_alts,
                value=(available_alts[0], available_alts[-1]),
                key=self.get_key('resist_alt'),
                help="Select the range of JJ lengths (alt) to include"
            )
            selected_alts = [v for v in available_alts if alt_range[0] <= v <= alt_range[1]]
        else:
            st.info(f"Only one JJ length available: {available_alts[0]} µm")
            selected_alts = available_alts

        available_dias = sorted(resist_df['dia'].dropna().unique().tolist())
        selected_dias = st.multiselect(
            "Bridge width — dia (µm):",
            available_dias,
            default=available_dias,
            key=self.get_key('resist_dia'),
            help="dia = bridge / undercut width"
        )

        if not selected_alts or not selected_dias:
            st.info("Select JJ length range and bridge width to continue.")
            return

        resist_df = resist_df[
            resist_df['alt'].isin(selected_alts) &
            resist_df['dia'].isin(selected_dias)
        ].copy()

        # Add day number and base wafer (helpers defined at top of render)
        resist_df['day_sort_key'] = resist_df['Wafer'].apply(extract_day_number)
        resist_df['base_wafer'] = resist_df['Wafer'].apply(extract_base_wafer_name)
        resist_df = resist_df[resist_df['day_sort_key'] != 999].copy()

        if resist_df.empty:
            st.warning("No wafers with DayX naming found in the filtered resistance data.")
            return

        # Wafer selection (by base name, same pattern as section 1)
        unique_base_wafers_r = sorted(resist_df['base_wafer'].unique())
        selected_base_wafers_r = st.multiselect(
            "Select wafers to plot (by base name):",
            unique_base_wafers_r,
            default=unique_base_wafers_r,
            key=self.get_key('resist_base_wafers')
        )

        if not selected_base_wafers_r:
            st.warning("Please select at least one wafer to plot.")
            return

        resist_df = resist_df[resist_df['base_wafer'].isin(selected_base_wafers_r)].copy()

        st.write(
            f"**{len(resist_df)} data points** — "
            f"{resist_df['Wafer'].nunique()} wafer(s), {resist_df['Die'].nunique()} die(s)"
        )

        # Step 3 — plot options
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            color_by_r = st.selectbox(
                "Color by:",
                ['Die', 'base_wafer', 'Option'],
                index=0,
                key=self.get_key('resist_color')
            )
        with col_p2:
            connect_lines = st.checkbox(
                "Connect same Die across days",
                value=True,
                key=self.get_key('resist_lines'),
                help="Lines connect the same Die position within the same base wafer"
            )
        with col_p3:
            log_r = st.checkbox("Log scale Y", value=False, key=self.get_key('resist_log'))

        # Build color map
        color_col_r = color_by_r  # all options are already valid column names
        all_color_vals = sorted(resist_df[color_col_r].dropna().astype(str).unique())
        color_map_r = {v: colors[i % len(colors)] for i, v in enumerate(all_color_vals)}

        fig_r = go.Figure()
        shown_legend: set = set()

        # One trace per (base_wafer, Die) so lines never cross different samples
        for bw in sorted(resist_df['base_wafer'].unique()):
            bw_df = resist_df[resist_df['base_wafer'] == bw]
            for die in sorted(bw_df['Die'].unique()):
                die_df = bw_df[bw_df['Die'] == die].sort_values('day_sort_key')

                color_key = str(die_df[color_col_r].iloc[0])
                assigned_color = color_map_r.get(color_key, 'gray')
                first_occurrence = color_key not in shown_legend
                shown_legend.add(color_key)

                y_vals = np.log10(die_df['Resistance']) if log_r else die_df['Resistance']

                fig_r.add_trace(go.Scatter(
                    x=die_df['day_sort_key'],
                    y=y_vals,
                    mode='lines+markers' if connect_lines else 'markers',
                    name=color_key,
                    legendgroup=color_key,
                    showlegend=first_occurrence,
                    marker=dict(size=8, color=assigned_color),
                    line=dict(color=assigned_color, width=1.5),
                    text=(
                        die_df['Wafer'] + ' | Die: ' + die_df['Die'].astype(str) +
                        ' | TS: ' + die_df['TS'].astype(str) +
                        ' | alt: ' + die_df['alt'].astype(str) +
                        ' | dia: ' + die_df['dia'].astype(str)
                    ),
                    customdata=np.column_stack([
                        die_df['Resistance'], die_df['alt'], die_df['dia']
                    ]),
                    hovertemplate=(
                        '%{text}<br>'
                        'Day: %{x}<br>'
                        'Resistance: %{customdata[0]:.1f} Ω<br>'
                        'alt: %{customdata[1]} µm | dia: %{customdata[2]} µm'
                        '<extra></extra>'
                    )
                ))

        fig_r.update_layout(
            title="Dolan JJ Resistance vs Day Number",
            xaxis_title="Day Number",
            yaxis_title="log₁₀(Resistance [Ω])" if log_r else "Resistance (Ω)",
            showlegend=True,
            height=600,
            hovermode='closest'
        )
        fig_r.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig_r.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')

        st.plotly_chart(fig_r, use_container_width=True)

        # ---- Linear fit: aging rate per (Die, alt) ----
        st.subheader("📈 Aging Rate vs JJ Length — per Die Linear Fit")
        st.caption(
            "For each (Die × JJ length) combination, a linear fit "
            "Resistance = slope × Day + intercept is performed across all selected wafers. "
            "Each point in the plots below is one Die."
        )

        fit_results = []
        for (die, alt_val), group in resist_df.groupby(['Die', 'alt']):
            x = group['day_sort_key'].values.astype(float)
            y = group['Resistance'].values.astype(float)
            valid = np.isfinite(x) & np.isfinite(y)
            x, y = x[valid], y[valid]
            if len(x) < 3:
                continue
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            fit_results.append({
                'Die': die,
                'alt (µm)': alt_val,
                'slope (Ω/day)': slope,
                'slope_stderr': std_err,
                'intercept (Ω)': intercept,
                'R²': r_value ** 2,
                'p_value': p_value,
                'n_points': len(x),
                'n_wafers': int(group['Wafer'].nunique()),
            })

        if not fit_results:
            st.info("Not enough data points per (Die, JJ length) to fit (need ≥ 3 days per combination).")
        else:
            fit_df = pd.DataFrame(fit_results)

            # Color by Die — reuse the same color palette
            unique_dies_fit = sorted(fit_df['Die'].unique())
            die_color_map = {d: colors[i % len(colors)] for i, d in enumerate(unique_dies_fit)}

            fig_fit = make_subplots(
                rows=1, cols=2,
                subplot_titles=("Slope (Ω/day) vs JJ Length", "R² vs JJ Length"),
            )

            shown_fit_legend: set = set()
            for die in unique_dies_fit:
                die_df = fit_df[fit_df['Die'] == die].sort_values('alt (µm)')
                color = die_color_map[die]
                show_leg = die not in shown_fit_legend
                shown_fit_legend.add(die)

                hover = [
                    f"Die: {row['Die']}<br>"
                    f"alt: {row['alt (µm)']} µm<br>"
                    f"slope: {row['slope (Ω/day)']:.4f} ± {row['slope_stderr']:.4f} Ω/day<br>"
                    f"R²: {row['R²']:.3f}<br>"
                    f"p: {row['p_value']:.3e}<br>"
                    f"n = {row['n_points']} days, {row['n_wafers']} wafers"
                    for _, row in die_df.iterrows()
                ]

                common = dict(
                    x=die_df['alt (µm)'],
                    mode='markers',
                    name=str(die),
                    legendgroup=str(die),
                    marker=dict(size=9, color=color),
                    text=hover,
                    hovertemplate='%{text}<extra></extra>',
                )

                fig_fit.add_trace(
                    go.Scatter(**common,
                               y=die_df['slope (Ω/day)'],
                               error_y=dict(type='data', array=die_df['slope_stderr'],
                                            visible=True, thickness=1.5, width=5),
                               showlegend=show_leg),
                    row=1, col=1,
                )
                fig_fit.add_trace(
                    go.Scatter(**common,
                               y=die_df['R²'],
                               showlegend=False),
                    row=1, col=2,
                )

            fig_fit.add_hline(y=0, line_dash='dash', line_color='gray', row=1, col=1)
            fig_fit.update_yaxes(range=[0, 1], row=1, col=2)
            fig_fit.update_xaxes(title_text="JJ Length — alt (µm)", row=1, col=1)
            fig_fit.update_xaxes(title_text="JJ Length — alt (µm)", row=1, col=2)
            fig_fit.update_yaxes(title_text="Slope (Ω/day)", row=1, col=1)
            fig_fit.update_yaxes(title_text="R²", row=1, col=2)
            fig_fit.update_layout(height=450, hovermode='closest')

            st.plotly_chart(fig_fit, use_container_width=True)

            display_cols = ['Die', 'alt (µm)', 'slope (Ω/day)', 'slope_stderr', 'intercept (Ω)', 'R²', 'p_value', 'n_points', 'n_wafers']
            st.dataframe(
                fit_df[display_cols].sort_values(['alt (µm)', 'Die']).round(4),
                use_container_width=True, hide_index=True
            )

            # ---- Normalized aging rate: slope / R₀ (%/day) vs JJ length ----
            st.subheader("📊 Normalized Aging Rate (%/day) vs JJ Length")

            valid_fit_df = fit_df[fit_df['intercept (Ω)'] > 0].copy()
            valid_fit_df['slope_%/day'] = (
                valid_fit_df['slope (Ω/day)'] / valid_fit_df['intercept (Ω)'] * 100
            )
            valid_fit_df['slope_%/day_err'] = (
                valid_fit_df['slope_stderr'] / valid_fit_df['intercept (Ω)'] * 100
            )

            if valid_fit_df.empty:
                st.warning("No valid normalized aging rate (all fit intercepts ≤ 0).")
            else:
                fig_pct = go.Figure()
                shown_legend_pct: set = set()

                for die in sorted(valid_fit_df['Die'].unique()):
                    die_data = valid_fit_df[valid_fit_df['Die'] == die].sort_values('alt (µm)')
                    color = die_color_map.get(die, 'gray')
                    first_occ = die not in shown_legend_pct
                    shown_legend_pct.add(die)

                    hover = [
                        f"Die: {row['Die']}<br>"
                        f"alt: {row['alt (µm)']} µm<br>"
                        f"Slope: {row['slope (Ω/day)']:.4f} Ω/day<br>"
                        f"R₀ (intercept): {row['intercept (Ω)']:.2f} Ω<br>"
                        f"Normalized: {row['slope_%/day']:.4f} ± {row['slope_%/day_err']:.4f} %/day<br>"
                        f"R²: {row['R²']:.3f}"
                        for _, row in die_data.iterrows()
                    ]

                    fig_pct.add_trace(go.Scatter(
                        x=die_data['alt (µm)'],
                        y=die_data['slope_%/day'],
                        mode='markers',
                        name=str(die),
                        legendgroup=str(die),
                        showlegend=first_occ,
                        marker=dict(size=9, color=color),
                        error_y=dict(
                            type='data',
                            array=die_data['slope_%/day_err'],
                            visible=True, thickness=1.5, width=5
                        ),
                        text=hover,
                        hovertemplate='%{text}<extra></extra>',
                    ))

                fig_pct.add_hline(y=0, line_dash='dash', line_color='gray')
                fig_pct.update_xaxes(title_text="JJ Length — alt (µm)", showgrid=True, gridwidth=1, gridcolor='lightgray')
                fig_pct.update_yaxes(title_text="Normalized Aging Rate (%/day)", showgrid=True, gridwidth=1, gridcolor='lightgray')
                fig_pct.update_layout(
                    title="Normalized Aging Rate (%/day) vs JJ Length — per Die",
                    height=420, hovermode='closest'
                )

                st.plotly_chart(fig_pct, use_container_width=True)
                st.caption(
                    "**Y axis:** slope (Ω/day) ÷ intercept (Ω) × 100 = % resistance change per day. "
                    "The intercept is the fitted resistance at Day 0 (R₀), used as the reference. "
                    "Normalizing by R₀ removes the dependence on absolute resistance, "
                    "making aging rates comparable across different JJ lengths and die positions. "
                    "Error bars propagate the slope standard error: σ_norm = σ_slope / R₀ × 100."
                )

        # Summary table
        st.subheader("📋 Resistance Summary by Day")
        summary_r = (
            resist_df.groupby(['day_sort_key', 'Die'])['Resistance']
            .agg(['mean', 'std', 'count'])
            .reset_index()
        )
        summary_r.columns = ['Day', 'Die', 'Mean Resistance (Ω)', 'Std (Ω)', 'N']
        st.dataframe(summary_r.sort_values(['Day', 'Die']).round(2), use_container_width=True, hide_index=True)

        # Export
        export_r = resist_df[['Wafer', 'Die', 'TS', 'Option', 'alt', 'dia', 'Resistance', 'day_sort_key', 'base_wafer']].copy()
        export_r = export_r.rename(columns={'day_sort_key': 'Day_Number'})
        st.download_button(
            label="📥 Download Resistance Data (CSV)",
            data=export_r.to_csv(index=False),
            file_name="jj_aging_resistance.csv",
            mime="text/csv",
            key=self.get_key('resist_download')
        )
