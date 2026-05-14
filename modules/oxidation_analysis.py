"""
Oxidation Analysis Module

This module provides oxidation dose analysis functionality for the 
DC Test Structure Analysis Dashboard.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc
from scipy import stats
from scipy.integrate import simpson
from .base import AnalysisModule


class OxidationAnalysisModule(AnalysisModule):
    """Oxidation dose analysis module"""
    
    def render(self, df, **kwargs):
        st.header("🧪 Jc vs Oxidation Dose")
        
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

        # Load oxidation dose data
        oxidation_df = self.db_manager.load_metadata_table('Fab_Process_Parameter')

        # Prepare data for scatter plot
        # Ensure unique Jc values using Die for each wafer
        df = df.drop_duplicates(subset=['Wafer', 'Die', 'Option'])

        # Merge oxidation dose data and processing date
        df = df.merge(oxidation_df[['Wafer', 'Oxidation Dose (Torr-min)', 'processing_date']], on='Wafer', how='left')

        # Filter out rows with missing oxidation dose data
        df_filtered = df[(df['Oxidation Dose (Torr-min)'].notna()) & (df['Oxidation Dose (Torr-min)'] > 0)]

        # PLOT: Jc_by_die_considering_offset vs Oxidation Dose
        st.subheader("📊 Jc (Considering Offset) vs Oxidation Dose")
        # write how many unique wafers and dies are in the filtered data
        st.write(f"Data points from {df_filtered['Wafer'].nunique()} unique wafers and {df_filtered['Die'].nunique()} unique dies.")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            color_by = st.selectbox("Color points by:", ['Option', 'Wafer', 'Die'], index=1, key="color_by")
        with col2:
            marker_by = st.selectbox("Marker type by:", ['None', 'Option', 'Wafer', 'Die'], index=3, key="marker_by")
        with col3:
            perform_fit = st.checkbox("Perform linear fit", value=True, key="fit")
        with col4:
            target_jc = st.number_input("Target Jc (µA/µm²):", min_value=0.0, max_value=5.0, value=0.5, step=0.1, key="target_jc")

        # Filter data - always use Jc_by_die_considering_offset
        plot_data = df_filtered[(df_filtered[jc_type].notna()) & (df_filtered[jc_type] > 0)]
        
        if not plot_data.empty:
            fig = go.Figure()
            fig.update_layout(width=400, height=600)
            
            # Define marker symbols for different categories
            marker_symbols = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'triangle-down', 'pentagon', 'hexagon', 'star']
            
            # Get unique values for color and marker assignments
            color_values = sorted([v for v in plot_data[color_by].unique() if pd.notna(v)])
            
            # Create color map using plotly default colors
            colors = pc.qualitative.Plotly + pc.qualitative.Set1 + pc.qualitative.Set2
            color_map = {val: colors[i % len(colors)] for i, val in enumerate(color_values)}
            
            # Handle marker assignment
            if marker_by == 'None':
                # Use default circle marker for all
                marker_values = []
                marker_map = {}
            else:
                marker_values = sorted([v for v in plot_data[marker_by].unique() if pd.notna(v)])
                marker_map = {val: marker_symbols[i % len(marker_symbols)] for i, val in enumerate(marker_values)}
            
            # If marker_by is None or if color_by and marker_by are the same, use single trace per color value
            if marker_by == 'None' or color_by == marker_by:
                for value in color_values:
                    filtered_data = plot_data[plot_data[color_by] == value]
                    # Use circle for None, otherwise get from marker_map
                    marker_symbol = 'circle' if marker_by == 'None' else marker_map.get(value, 'circle')
                    color = color_map.get(value)
                    fig.add_trace(go.Scatter(
                        x=np.log10(filtered_data['Oxidation Dose (Torr-min)']),
                        y=np.log10(filtered_data[jc_type]),
                        mode='markers',
                        name=f"{value}",
                        marker=dict(symbol=marker_symbol, size=10, color=color),
                        text=filtered_data['Wafer'] + ', Die: ' + filtered_data['Die'].astype(str) + ', Option: ' + filtered_data['Option'],
                        customdata=np.column_stack([filtered_data['Oxidation Dose (Torr-min)'], filtered_data[jc_type]]),
                        hovertemplate='%{text}<br>Oxidation Dose: %{customdata[0]:.3f} Torr-min<br>Jc: %{customdata[1]:.3f} µA/µm²<extra></extra>'
                    ))
            else:
                # Group by both color and marker categories
                for color_value in color_values:
                    color_filtered = plot_data[plot_data[color_by] == color_value]
                    assigned_color = color_map.get(color_value)
                    
                    for marker_value in marker_values:
                        marker_filtered = color_filtered[color_filtered[marker_by] == marker_value]
                        if not marker_filtered.empty:
                            marker_symbol = marker_map.get(marker_value, 'circle')
                            legend_name = f"{color_value} ({marker_by}: {marker_value})"
                            fig.add_trace(go.Scatter(
                                x=np.log10(marker_filtered['Oxidation Dose (Torr-min)']),
                                y=np.log10(marker_filtered[jc_type]),
                                mode='markers',
                                name=legend_name,
                                marker=dict(symbol=marker_symbol, size=10, color=assigned_color),
                                text=marker_filtered['Wafer'] + ', Die: ' + marker_filtered['Die'].astype(str) + ', Option: ' + marker_filtered['Option'],
                                customdata=np.column_stack([marker_filtered['Oxidation Dose (Torr-min)'], marker_filtered[jc_type]]),
                                hovertemplate='%{text}<br>Oxidation Dose: %{customdata[0]:.3f} Torr-min<br>Jc: %{customdata[1]:.3f} µA/µm²<extra></extra>'
                            ))

            # Perform linear fit if requested
            if perform_fit and len(plot_data) >= 2:
                # Prepare data for fitting (all data points combined)
                x_data = np.log10(plot_data['Oxidation Dose (Torr-min)'])
                y_data = np.log10(plot_data[jc_type])
                
                # Remove any NaN or infinite values
                valid_mask = ~(np.isnan(x_data) | np.isnan(y_data) | np.isinf(x_data) | np.isinf(y_data))
                x_fit = x_data[valid_mask]
                y_fit = y_data[valid_mask]
                
                if len(x_fit) >= 2:
                    # Perform linear regression
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x_fit, y_fit)
                    
                    # Create fit line
                    x_line = np.linspace(x_fit.min(), x_fit.max(), 100)
                    y_line = slope * x_line + intercept
                    
                    # Add fit line to plot
                    fig.add_trace(go.Scatter(
                        x=x_line,
                        y=y_line,
                        mode='lines',
                        line=dict(color='black', width=2, dash='dash'),
                        name=f'Linear Fit (R² = {r_value**2:.3f})',
                        showlegend=True
                    ))
                    
                    # Display fit results
                    st.subheader("📊 Linear Fit Results")
                    col1_fit, col2_fit = st.columns(2)
                    
                    with col1_fit:
                        st.metric("Slope", f"{slope:.3f}")
                        st.metric("R² Value", f"{r_value**2:.3f}")
                        st.metric("P-value", f"{p_value:.2e}")
                    
                    with col2_fit:
                        st.metric("Intercept", f"{intercept:.3f}")
                        st.metric("Std Error", f"{std_err:.3f}")
                        st.metric("Data Points", f"{len(x_fit)}")
                    
                    # Display fit equation
                    st.markdown(f"""
                    **Fit Equation:**
                    
                    log₁₀(Jc considering offset) = {slope:.3f} × log₁₀(Dose) + {intercept:.3f}
                    
                    **In linear form:**
                    
                    Jc considering offset = 10^({intercept:.3f}) × Dose^({slope:.3f})
                    """)
                    
                    # Add prediction point if target Jc is provided
                    if target_jc > 0:
                        log_target_jc = np.log10(target_jc)
                        predicted_log_dose = (log_target_jc - intercept) / slope
                        predicted_dose = 10**predicted_log_dose
                        
                        # Add target point to plot
                        fig.add_trace(go.Scatter(
                            x=[predicted_log_dose],
                            y=[log_target_jc],
                            mode='markers',
                            marker=dict(size=15, color='orange', symbol='star'),
                            name=f'Target: Jc={target_jc:.2f}',
                            hovertemplate=f'Target Jc: {target_jc:.2f} µA/µm²<br>Predicted Dose: {predicted_dose:.3f} Torr-min<extra></extra>'
                        ))
                        
                        st.success(f"🎯 For Jc considering offset = {target_jc:.2f} µA/µm², predicted oxidation dose = **{predicted_dose:.3f} Torr·min**")

            fig.update_layout(
                title=f"Jc (Considering Offset) vs Oxidation Dose (Log-Log Scale) - {jj_category}",
                xaxis_title="log₁₀(Oxidation Dose [Torr-min])",
                yaxis_title="log₁₀(Jc Considering Offset [µA/µm²])",
                showlegend=True,
                height=500
            )

            st.plotly_chart(fig, use_container_width=True)
            
            # ========================================
            # Linear Scale Plot
            # ========================================
            st.subheader("📈 Jc vs Oxidation Dose (Linear Scale)")
            
            fig_linear = go.Figure()
            
            # Use the same color and marker mapping as log-log plot
            if marker_by == 'None' or color_by == marker_by:
                for value in color_values:
                    filtered_data = plot_data[plot_data[color_by] == value]
                    # Use circle for None, otherwise get from marker_map
                    marker_symbol = 'circle' if marker_by == 'None' else marker_map.get(value, 'circle')
                    color = color_map.get(value)
                    fig_linear.add_trace(go.Scatter(
                        x=filtered_data['Oxidation Dose (Torr-min)'],
                        y=filtered_data[jc_type],
                        mode='markers',
                        name=f"{value}",
                        marker=dict(symbol=marker_symbol, size=10, color=color),
                        text=filtered_data['Wafer'] + ', Die: ' + filtered_data['Die'].astype(str) + ', Option: ' + filtered_data['Option'],
                        customdata=np.column_stack([filtered_data['Oxidation Dose (Torr-min)'], filtered_data[jc_type]]),
                        hovertemplate='%{text}<br>Oxidation Dose: %{customdata[0]:.3f} Torr-min<br>Jc: %{customdata[1]:.3f} µA/µm²<extra></extra>'
                    ))
            else:
                # Group by both color and marker categories
                for color_value in color_values:
                    color_filtered = plot_data[plot_data[color_by] == color_value]
                    assigned_color = color_map.get(color_value)
                    
                    for marker_value in marker_values:
                        marker_filtered = color_filtered[color_filtered[marker_by] == marker_value]
                        if not marker_filtered.empty:
                            marker_symbol = marker_map.get(marker_value, 'circle')
                            legend_name = f"{color_value} ({marker_by}: {marker_value})"
                            fig_linear.add_trace(go.Scatter(
                                x=marker_filtered['Oxidation Dose (Torr-min)'],
                                y=marker_filtered[jc_type],
                                mode='markers',
                                name=legend_name,
                                marker=dict(symbol=marker_symbol, size=10, color=assigned_color),
                                text=marker_filtered['Wafer'] + ', Die: ' + marker_filtered['Die'].astype(str) + ', Option: ' + marker_filtered['Option'],
                                customdata=np.column_stack([marker_filtered['Oxidation Dose (Torr-min)'], marker_filtered[jc_type]]),
                                hovertemplate='%{text}<br>Oxidation Dose: %{customdata[0]:.3f} Torr-min<br>Jc: %{customdata[1]:.3f} µA/µm²<extra></extra>'
                            ))
            
            fig_linear.update_layout(
                title=f"Jc (Considering Offset) vs Oxidation Dose (Linear Scale) - {jj_category}",
                xaxis_title="Oxidation Dose [Torr-min]",
                yaxis_title="Jc Considering Offset [µA/µm²]",
                showlegend=True,
                height=500
            )
            
            st.plotly_chart(fig_linear, use_container_width=True)

            # ========================================
            # Download Data Section
            # ========================================
            st.subheader("📥 Download Data")
            
            # Prepare data for download
            download_data = plot_data[[
                'Wafer', 'Die', 'Option', 
                'processing_date',
                'Oxidation Dose (Torr-min)', 
                jc_type
            ]].copy()
            
            # Rename columns for clarity in exported file
            download_data.columns = [
                'Wafer', 'Die', 'Option', 
                'Processing Date',
                'Oxidation Dose (Torr-min)', 
                'Jc Considering Offset (µA/µm²)'
            ]
            
            # Convert to CSV
            csv = download_data.to_csv(index=False)
            
            # Create download button
            st.download_button(
                label="📊 Download Plot Data (CSV)",
                data=csv,
                file_name=f"oxidation_jc_analysis_{jj_category}.csv",
                mime="text/csv",
                key="download_plot_data"
            )
            
            # Display statistics about the download
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("Total Data Points", len(download_data))
            with col_stats2:
                st.metric("Unique Wafers", download_data['Wafer'].nunique())
            with col_stats3:
                st.metric("Unique Options", download_data['Option'].nunique())

            # 
            
        else:
            st.warning("No valid data found for the plot.")



        
        # # ========================================
        # # Oxidation Process Reproducibility Section
        # # ========================================
        # st.divider()
        # st.header("🔬 Oxidation Process Reproducibility")
        # st.subheader("Cumulative Dose Curves")
        
        # # Filter oxidation data to only show wafers in current selection
        # if selected_wafers is not None and len(selected_wafers) > 0:
        #     oxidation_df_filtered = oxidation_df[oxidation_df['Wafer'].isin(selected_wafers)]
        # else:
        #     oxidation_df_filtered = oxidation_df
        
        # # Check if we have the required columns
        # if 'Oxidation Pressure (Torr)' not in oxidation_df_filtered.columns or 'Oxidation Time (min)' not in oxidation_df_filtered.columns:
        #     st.warning("Oxidation Pressure and Time data not available in database.")
        #     return
        
        # # Parse and calculate cumulative dose for each wafer
        # cumulative_data = []
        
        # for idx, row in oxidation_df_filtered.iterrows():
        #     wafer = row['Wafer']
        #     pressure_str = row['Oxidation Pressure (Torr)']
        #     time_str = row['Oxidation Time (min)']
            
        #     # Skip if either field is None or NaN
        #     if pd.isna(pressure_str) or pd.isna(time_str):
        #         continue
            
        #     try:
        #         # Parse arrays - handle both string representation and actual lists
        #         if isinstance(pressure_str, str):
        #             # Remove brackets and split by comma
        #             pressure_str = pressure_str.strip('[]')
        #             pressure_values = [float(x.strip()) for x in pressure_str.split(',') if x.strip()]
        #         else:
        #             pressure_values = pressure_str if isinstance(pressure_str, list) else [pressure_str]
                
        #         if isinstance(time_str, str):
        #             time_str = time_str.strip('[]')
        #             time_values = [float(x.strip()) for x in time_str.split(',') if x.strip()]
        #         else:
        #             time_values = time_str if isinstance(time_str, list) else [time_str]
                
        #         # Ensure arrays have same length
        #         if len(pressure_values) != len(time_values):
        #             st.warning(f"Wafer {wafer}: Pressure and time arrays have different lengths. Skipping.")
        #             continue
                
        #         # Convert to numpy arrays
        #         pressures = np.array(pressure_values)
        #         times = np.array(time_values)  # Already cumulative times in minutes from start
                
        #         # Prepend t=0 at the beginning
        #         cumulative_time = np.concatenate([[0], times])
        #         # Prepend first pressure value at t=0 (assume constant pressure at start)
        #         pressures_with_start = np.concatenate([[pressures[0]], pressures])
                
        #         # Calculate cumulative dose using Simpson's Rule
        #         # For each time point i, integrate from 0 to i using Simpson's Rule
        #         cumulative_dose = []
        #         for i in range(len(cumulative_time)):
        #             if i == 0:
        #                 cumulative_dose.append(0.0)
        #             elif i == 1:
        #                 # For just 2 points, use trapezoidal rule
        #                 dose = 0.5 * (pressures_with_start[0] + pressures_with_start[1]) * cumulative_time[1]
        #                 cumulative_dose.append(dose)
        #             else:
        #                 # Use Simpson's Rule for 3+ points
        #                 dose = simpson(pressures_with_start[:i+1], cumulative_time[:i+1])
        #                 cumulative_dose.append(dose)
                
        #         cumulative_dose = np.array(cumulative_dose)
                
        #         # Store data (remove the prepended t=0 point for display consistency)
        #         cumulative_data.append({
        #             'Wafer': wafer,
        #             'Cumulative_Time': cumulative_time[1:].tolist(),  # Skip t=0
        #             'Cumulative_Dose': cumulative_dose[1:].tolist(),  # Skip dose=0
        #             'Final_Dose': cumulative_dose[-1] if len(cumulative_dose) > 0 else 0
        #         })
                
        #     except Exception as e:
        #         st.warning(f"Error parsing data for wafer {wafer}: {str(e)}")
        #         continue
        
        # if not cumulative_data:
        #     st.warning("No valid oxidation profile data found for selected wafers.")
        #     return
        
        # # Sort cumulative_data by wafer name to ensure consistent color ordering
        # cumulative_data = sorted(cumulative_data, key=lambda x: x['Wafer'])
        
        # # Create the cumulative dose plot
        # fig_dose = go.Figure()
        
        # # Use colormap for wafers - same color scheme as main plot
        # colors = pc.qualitative.Plotly + pc.qualitative.Set1 + pc.qualitative.Set2
        
        # # Create color map based on sorted wafer names (consistent with main plot when color_by='Wafer')
        # wafer_names_sorted = [data['Wafer'] for data in cumulative_data]
        # color_map = {wafer: colors[i % len(colors)] for i, wafer in enumerate(wafer_names_sorted)}
        
        # for data in cumulative_data:
        #     wafer = data['Wafer']
        #     cum_time = data['Cumulative_Time']
        #     cum_dose = data['Cumulative_Dose']
        #     color = color_map[wafer]
            
        #     # Add cumulative time = 0, dose = 0 at the beginning
        #     cum_time_plot = [0] + cum_time
        #     cum_dose_plot = [0] + cum_dose
            
        #     fig_dose.add_trace(go.Scatter(
        #         x=cum_time_plot,
        #         y=cum_dose_plot,
        #         mode='lines+markers',
        #         name=wafer,
        #         line=dict(width=2, color=color),
        #         marker=dict(size=6, color=color),
        #         hovertemplate=f'{wafer}<br>Time: %{{x:.2f}} min<br>Cumulative Dose: %{{y:.4f}} Torr·min<extra></extra>'
        #     ))
        
        # fig_dose.update_layout(
        #     title="Cumulative Oxidation Dose Over Time",
        #     xaxis_title="Cumulative Time (min)",
        #     yaxis_title="Cumulative Dose (Torr·min)",
        #     showlegend=True,
        #     height=600,
        #     hovermode='closest'
        # )
        
        # st.plotly_chart(fig_dose, use_container_width=True)
        
        # # Display statistics
        # st.subheader("📊 Dose Statistics")
        
        # # Create summary table
        # summary_data = []
        # for data in cumulative_data:
        #     summary_data.append({
        #         'Wafer': data['Wafer'],
        #         'Final Dose (Torr·min)': f"{data['Final_Dose']:.4f}",
        #         'Total Time (min)': f"{data['Cumulative_Time'][-1]:.2f}" if data['Cumulative_Time'] else "N/A"
        #     })
        
        # summary_df = pd.DataFrame(summary_data)
        # st.dataframe(summary_df, use_container_width=True)
        
        # # Calculate and display variability metrics
        # if len(cumulative_data) > 1:
        #     final_doses = [data['Final_Dose'] for data in cumulative_data]
        #     mean_dose = np.mean(final_doses)
        #     std_dose = np.std(final_doses, ddof=1)
        #     cv_percent = (std_dose / mean_dose * 100) if mean_dose > 0 else 0
            
        #     col1, col2, col3 = st.columns(3)
        #     with col1:
        #         st.metric("Mean Final Dose", f"{mean_dose:.4f} Torr·min")
        #     with col2:
        #         st.metric("Std Deviation", f"{std_dose:.4f} Torr·min")
        #     with col3:
        #         st.metric("CV%", f"{cv_percent:.2f}%")