"""
Database Summary Analysis Module

This module provides comprehensive database overview and table exploration
functionality for the DC Test Structure Analysis Dashboard.
"""

import streamlit as st
from components.database_utility import get_table_names, get_table_info, load_table_data
from .base import AnalysisModule


class DatabaseSummaryModule(AnalysisModule):
    """Database summary and exploration module"""
    
    def render(self, df, **kwargs):
        st.header("📊 Database Summary")
        
        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)
        
        # Database overview
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(df))
        with col2:
            st.metric("Total Wafers", df['Wafer'].nunique() if 'Wafer' in df.columns else 0)
        with col3:
            st.metric("Analysis Options", df['Option'].nunique() if 'Option' in df.columns else 0)
        with col4:
            if selected_wafers:
                st.metric("Selected Wafers", len(selected_wafers))
            else:
                st.metric("All Wafers", "No filter")
        
        # Table exploration
        st.subheader("🗂️ Table Explorer")
        all_tables = get_table_names()
        
        selected_table = st.selectbox(
            "Select table to explore:",
            all_tables,
            help="Choose a table to view its structure and data"
        )
        
        if selected_table:
            table_info = get_table_info(selected_table)
            table_data = load_table_data(selected_table)
            
            if table_info:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader(f"📋 Table: {selected_table}")
                    st.write(f"**Rows:** {table_info['row_count']}")
                    st.write(f"**Columns:** {table_info['column_count']}")
                    
                    with st.expander("📝 Column Details"):
                        st.dataframe(table_info['schema'], use_container_width=True)
                
                with col2:
                    if not table_data.empty:
                        st.subheader("🔍 Data Preview")
                        st.dataframe(table_data.head(10), use_container_width=True)