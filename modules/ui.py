from decimal import Decimal, ROUND_HALF_UP

import streamlit as st
from num2words import num2words


def amount_in_words(value):
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    absolute_amount = abs(amount)
    whole_amount = int(absolute_amount)
    paise = int((absolute_amount - whole_amount) * 100)
    words = num2words(whole_amount, lang="en")
    result = f"{'Minus ' if amount < 0 else ''}{words} rupees"
    if paise:
        result += f" and {num2words(paise, lang='en')} paise"
    return result[0].upper() + result[1:]


def amount_input_with_words(label, key, value=0.0):
    amount = st.number_input(
        label,
        min_value=0.0,
        step=0.01,
        format="%.2f",
        value=float(value or 0),
        key=key,
    )
    st.caption(amount_in_words(amount))
    return amount


def flash_success(message):
    st.session_state["_flash_success_message"] = message
    st.rerun()


def show_flash_message():
    message = st.session_state.pop("_flash_success_message", None)
    if message:
        st.success(message)


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