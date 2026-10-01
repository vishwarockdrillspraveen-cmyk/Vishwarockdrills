import streamlit as st


def action_control(key, options, default):
    return st.segmented_control(
        "Page actions",
        options=options,
        default=default,
        key=key,
        label_visibility="collapsed",
        width="stretch",
        required=True,
    )