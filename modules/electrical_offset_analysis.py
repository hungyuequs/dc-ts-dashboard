"""
Electrical Offset Analysis Module
Analyzes electrical offset across wafers for Dolan and Manhattan junctions
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from .base import AnalysisModule


class ElectricalOffsetAnalysisModule(AnalysisModule):
    """Analysis module for electrical offset across wafers"""
    
    def render(self, df, **kwargs):
        """
        Render the electrical offset analysis interface
        
        Args:
            df: Main dataframe with measurement data
            **kwargs: Additional keyword arguments (e.g., selected_wafers)
        """
        # Filter data for relevant options
        Dolan_offset_data = df[df['Option'].str.contains('Dolan', case=False, na=False) & 
                    (df['Option'].str.contains('Const_L', case=False, na=False) | 
                        df['Option'].str.contains('Const_W', case=False, na=False))]
        Manhattan_offset_data = df[df['Option'].str.contains('Manhattan_JJ', case=False, na=False) & 
                    (df['Option'].str.contains('Const_V', case=False, na=False) | 
                        df['Option'].str.contains('Const_H', case=False, na=False))]
        
        if Dolan_offset_data.empty and Manhattan_offset_data.empty:
            st.error("No data found for offset analysis options (Dolan_JJ_Const_W, Dolan_JJ_Const_L, Manhattan_JJ_Const_H, Manhattan_JJ_Const_V)")
            st.info("Please ensure your data contains these analysis options.")
            return
        
        # Check for required columns
        required_dolan_columns = ['Dolan_BridgeWidth_offset', 'Dolan_BridgeLength_offset']
        required_manhattan_columns = ['Manhattan_HorizontalWidth_offset', 'Manhattan_VerticalWidth_offset']
        
        missing_dolan_columns = [col for col in required_dolan_columns if col not in df.columns] if not Dolan_offset_data.empty else []
        missing_manhattan_columns = [col for col in required_manhattan_columns if col not in df.columns] if not Manhattan_offset_data.empty else []
        
        if missing_dolan_columns and not Dolan_offset_data.empty:
            st.error(f"Required Dolan columns not found: {missing_dolan_columns}")
            st.info("Dolan analysis requires 'Dolan_BridgeWidth_offset' and 'Dolan_BridgeLength_offset' columns.")
            return
        elif missing_manhattan_columns and not Manhattan_offset_data.empty:
            st.error(f"Required Manhattan columns not found: {missing_manhattan_columns}")
            st.info("Manhattan analysis requires 'Manhattan_HorizontalWidth_offset' and 'Manhattan_VerticalWidth_offset' columns.")
            return
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🔧 Analysis Settings")

            # Dolan Options
            if not Dolan_offset_data.empty:
                st.subheader("📋 Dolan Options")
                
                # Separate Dolan options by Const_L and Const_W
                dolan_const_L_options = Dolan_offset_data[Dolan_offset_data['Option'].str.contains('Const_L', case=False, na=False)]['Option'].unique()
                dolan_const_W_options = Dolan_offset_data[Dolan_offset_data['Option'].str.contains('Const_W', case=False, na=False)]['Option'].unique()
                
                selected_dolan_const_L_options = st.multiselect(
                    "Select Dolan Const_L Analysis Options:",
                    dolan_const_L_options,
                    default=list(dolan_const_L_options),
                    key=self.get_key("dolan_const_L")
                )
                
                selected_dolan_const_W_options = st.multiselect(
                    "Select Dolan Const_W Analysis Options:",
                    dolan_const_W_options,
                    default=list(dolan_const_W_options),
                    key=self.get_key("dolan_const_W")
                )
                
                # Dolan Wafer selection
                all_dolan_options = list(selected_dolan_const_L_options) + list(selected_dolan_const_W_options)
                if all_dolan_options:
                    filtered_dolan_data = Dolan_offset_data[Dolan_offset_data['Option'].isin(all_dolan_options)]
                    # Sort the wafers in alphabetical order
                    available_wafers_dolan = filtered_dolan_data['Wafer'].unique()
                    available_wafers_dolan.sort()
                    selected_wafer_dolan = st.multiselect(
                        "Select Wafers for Dolan Analysis:",
                        available_wafers_dolan,
                        key=self.get_key("dolan_wafer")
                    )
            
            # Manhattan Options
            if not Manhattan_offset_data.empty:
                st.subheader("📋 Manhattan Options")
                
                # Separate Manhattan options by Const_V and Const_H
                manhattan_const_V_options = Manhattan_offset_data[Manhattan_offset_data['Option'].str.contains('Const_V', case=False, na=False)]['Option'].unique()
                manhattan_const_H_options = Manhattan_offset_data[Manhattan_offset_data['Option'].str.contains('Const_H', case=False, na=False)]['Option'].unique()
                
                selected_manhattan_const_V_options = st.multiselect(
                    "Select Manhattan Const_V Analysis Options:",
                    manhattan_const_V_options,
                    default=list(manhattan_const_V_options),
                    key=self.get_key("manhattan_const_V")
                )
                
                selected_manhattan_const_H_options = st.multiselect(
                    "Select Manhattan Const_H Analysis Options:",
                    manhattan_const_H_options,
                    default=list(manhattan_const_H_options),
                    key=self.get_key("manhattan_const_H")
                )
                
                # Manhattan Wafer selection
                all_manhattan_options = list(selected_manhattan_const_V_options) + list(selected_manhattan_const_H_options)
                if all_manhattan_options:
                    filtered_manhattan_data = Manhattan_offset_data[Manhattan_offset_data['Option'].isin(all_manhattan_options)]
                    available_wafers_manhattan = filtered_manhattan_data['Wafer'].unique()
                    available_wafers_manhattan.sort()
                    selected_wafer_manhattan = st.multiselect(
                        "Select Wafers for Manhattan Analysis:",
                        available_wafers_manhattan,
                        key=self.get_key("manhattan_wafer_electrical_offset")
                    )
            
            # Visualization settings
            st.subheader("🎨 Visualization Settings")
            color_by_offset = st.selectbox(
                "Color points by:",
                ['Option', 'Die'],
                index=0,
                key=self.get_key("color_by")
            )

        with col2:
            # Prepare data for each constraint type
            plot_data = {}
            
            # Dolan Const_L data
            if ('selected_dolan_const_L_options' in locals() and selected_dolan_const_L_options and 
                'selected_wafer_dolan' in locals() and selected_wafer_dolan):
                const_L_data = Dolan_offset_data[
                    (Dolan_offset_data['Option'].isin(selected_dolan_const_L_options)) &
                    (Dolan_offset_data['Wafer'].isin(selected_wafer_dolan)) &
                    (Dolan_offset_data['Dolan_BridgeWidth_offset'].notna())
                ].copy()
                if not const_L_data.empty:
                    # Invert the sign for electrical offset
                    const_L_data['electrical_offset'] = -1 * const_L_data['Dolan_BridgeWidth_offset']
                    const_L_data = const_L_data.drop_duplicates(subset=['Die', 'Wafer', 'Option'])
                    plot_data['Dolan_Const_L'] = const_L_data
            
            # Dolan Const_W data
            if ('selected_dolan_const_W_options' in locals() and selected_dolan_const_W_options and 
                'selected_wafer_dolan' in locals() and selected_wafer_dolan):
                const_W_data = Dolan_offset_data[
                    (Dolan_offset_data['Option'].isin(selected_dolan_const_W_options)) &
                    (Dolan_offset_data['Wafer'].isin(selected_wafer_dolan)) &
                    (Dolan_offset_data['Dolan_BridgeLength_offset'].notna())
                ].copy()
                if not const_W_data.empty:
                    const_W_data['electrical_offset'] = const_W_data['Dolan_BridgeLength_offset']
                    const_W_data = const_W_data.drop_duplicates(subset=['Die', 'Wafer', 'Option'])
                    plot_data['Dolan_Const_W'] = const_W_data
            
            # Manhattan Const_V data
            if ('selected_manhattan_const_V_options' in locals() and selected_manhattan_const_V_options and 
                'selected_wafer_manhattan' in locals() and selected_wafer_manhattan):
                const_V_data = Manhattan_offset_data[
                    (Manhattan_offset_data['Option'].isin(selected_manhattan_const_V_options)) &
                    (Manhattan_offset_data['Wafer'].isin(selected_wafer_manhattan)) &
                    (Manhattan_offset_data['Manhattan_HorizontalWidth_offset'].notna())
                ].copy()
                if not const_V_data.empty:
                    const_V_data['electrical_offset'] = const_V_data['Manhattan_HorizontalWidth_offset']
                    const_V_data = const_V_data.drop_duplicates(subset=['Die', 'Wafer', 'Option'])
                    plot_data['Manhattan_Const_V'] = const_V_data
            
            # Manhattan Const_H data
            if ('selected_manhattan_const_H_options' in locals() and selected_manhattan_const_H_options and 
                'selected_wafer_manhattan' in locals() and selected_wafer_manhattan):
                const_H_data = Manhattan_offset_data[
                    (Manhattan_offset_data['Option'].isin(selected_manhattan_const_H_options)) &
                    (Manhattan_offset_data['Wafer'].isin(selected_wafer_manhattan)) &
                    (Manhattan_offset_data['Manhattan_VerticalWidth_offset'].notna())
                ].copy()
                if not const_H_data.empty:
                    const_H_data['electrical_offset'] = const_H_data['Manhattan_VerticalWidth_offset']
                    const_H_data = const_H_data.drop_duplicates(subset=['Die', 'Wafer', 'Option'])
                    plot_data['Manhattan_Const_H'] = const_H_data

            if not plot_data:
                st.info("Please select analysis options and wafers to begin offset analysis.")
            else:
                def create_scatter_plot(data, color_by, title, y_label):
                    """Create a scatter plot for given data"""
                    if data.empty:
                        return None
                    
                    fig = go.Figure()
                    
                    # Get unique values for coloring
                    color_values = data[color_by].unique()
                    
                    # Create color palette
                    if len(color_values) <= 10:
                        color_palette = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
                    else:
                        import plotly.colors as pc
                        color_palette = pc.qualitative.Plotly * ((len(color_values) // len(pc.qualitative.Plotly)) + 1)
                    
                    color_map = {val: color_palette[i % len(color_palette)] for i, val in enumerate(color_values)}
                    
                    # Add scatter traces
                    for color_val in color_values:
                        subset = data[data[color_by] == color_val]
                        
                        if not subset.empty:
                            # Create hover text
                            hover_text = []
                            for _, row in subset.iterrows():
                                option = row['Option'] if 'Option' in row else 'N/A'
                                hover_base = (
                                    f"Wafer: {row['Wafer']}<br>"
                                    f"Die: {row.get('Die', 'N/A')}<br>"
                                    f"Option: {option}<br>"
                                    f"Electrical offset: {row['electrical_offset']:.3f} µm"
                                )
                                hover_text.append(hover_base)
                            
                            # Add scatter trace
                            fig.add_trace(go.Scatter(
                                x=subset['Wafer'],
                                y=subset['electrical_offset'],
                                mode='markers',
                                marker=dict(
                                    size=8, 
                                    color=color_map[color_val],
                                    opacity=0.7
                                ),
                                text=hover_text,
                                hovertemplate='%{text}<extra></extra>',
                                name=f'{color_by}: {color_val}'
                            ))
                    
                    # Update layout
                    fig.update_layout(
                        title=title,
                        xaxis_title="Wafer",
                        yaxis_title=y_label,
                        showlegend=True,
                        hovermode='closest',
                        height=450
                    )
                    
                    # Add grid and styling
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                    
                    return fig

                # Create individual plots for each constraint type
                plot_configs = {
                    'Dolan_Const_L': {
                        'title': 'JJ Width Process Bias (extract from JJ with Const L)',
                        'y_label': 'JJ Width Process Bias (µm)',
                        'section': '🔬 Dolan Analysis'
                    },
                    'Dolan_Const_W': {
                        'title': 'Dolan Bridge Length Offset (extract from JJ with Const W)',
                        'y_label': 'JJ Length Process Bias (µm)',
                        'section': '🔬 Dolan Analysis'
                    },
                    'Manhattan_Const_V': {
                        'title': 'Manhattan Horizontal Width Offset (Const_V)',
                        'y_label': 'Horizontal Width Offset (µm)',
                        'section': '🏢 Manhattan Analysis'
                    },
                    'Manhattan_Const_H': {
                        'title': 'Manhattan Vertical Width Offset (Const_H)',
                        'y_label': 'Vertical Width Offset (µm)',
                        'section': '🏢 Manhattan Analysis'
                    }
                }

                # Group plots by analysis type
                dolan_plots = []
                manhattan_plots = []
                
                for plot_key, data in plot_data.items():
                    if not data.empty:
                        config = plot_configs[plot_key]
                        fig = create_scatter_plot(
                            data, 
                            color_by_offset, 
                            config['title'], 
                            config['y_label']
                        )
                        if fig:
                            if 'Dolan' in plot_key:
                                dolan_plots.append((fig, config['title'], len(data)))
                            else:
                                manhattan_plots.append((fig, config['title'], len(data)))

                # Display Dolan plots
                if dolan_plots:
                    st.subheader("🔬 Dolan Junction Analysis")
                    for fig, title, n_points in dolan_plots:
                        st.info(f"{title}: {n_points} data points")
                        st.plotly_chart(fig, use_container_width=True)

                # Display Manhattan plots
                if manhattan_plots:
                    st.subheader("🏢 Manhattan Junction Analysis")
                    for fig, title, n_points in manhattan_plots:
                        st.info(f"{title}: {n_points} data points")
                        st.plotly_chart(fig, use_container_width=True)

                # Combined statistics summary
                st.subheader("📊 Electrical Offset Statistics")
                stats_data = []

                for plot_key, data in plot_data.items():
                    if not data.empty:
                        config = plot_configs[plot_key]
                        constraint_type = plot_key.split('_')[1]  # Extract Const_L, Const_W, etc.
                        
                        # Get unique options in this dataset
                        unique_options = data['Option'].unique()
                        
                        for option in unique_options:
                            option_data = data[data['Option'] == option]['electrical_offset']
                            
                            if not option_data.empty:
                                stats_data.append({
                                    'Constraint Type': constraint_type,
                                    'Option': option,
                                    'Offset Type': config['y_label'].replace(' (µm)', ''),
                                    'Mean (µm)': option_data.mean(),
                                    'Std (µm)': option_data.std(),
                                    'Min (µm)': option_data.min(),
                                    'Max (µm)': option_data.max(),
                                    'N Points': len(option_data)
                                })

                if stats_data:
                    stats_df = pd.DataFrame(stats_data).round(3)
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    
                    # Download button
                    all_data = pd.concat([data for data in plot_data.values() if not data.empty], ignore_index=True)
                    if not all_data.empty:
                        csv_offset = all_data.to_csv(index=False)
                        st.download_button(
                            label="📥 Download electrical offset analysis data",
                            data=csv_offset,
                            file_name=f"electrical_offset_analysis_{len(all_data)}_points.csv",
                            mime="text/csv",
                            key=self.get_key("download_data")
                        )
                else:
                    st.info("No statistics available for the selected options.")
