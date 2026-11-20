import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from answer import ask

st.set_page_config(page_title="ElectroMart Assistant", page_icon="🛒")
st.title("ElectroMart Indore Assistant")
st.caption("Ask about policies, SOPs and FAQs. Answers include citations.")


def to_dict(r):
    if isinstance(r, dict):
        return r
    if hasattr(r, "__dict__"):
        return vars(r)
    return {"answer": str(r)}


if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if q := st.chat_input("Ask a question, e.g. How long do I have to return a laptop?"):
    st.session_state.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            d = to_dict(ask(q))
        text = d.get("answer") or d.get("text") or str(d)
        st.markdown(text)
        sources = d.get("sources") or d.get("citations") or []
        if sources:
            st.markdown("**Sources**")
            for s in sources:
                st.markdown(f"- {s}")
        with st.expander("Raw result"):
            st.json(d, expanded=False)

    st.session_state.messages.append({"role": "assistant", "content": text})
