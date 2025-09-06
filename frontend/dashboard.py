
import os, time, json, requests, pandas as pd, matplotlib.pyplot as plt, streamlit as st

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="AI Communication Assistant", layout="wide")

st.title("📧 AI-Powered Communication Assistant")

colA, colB = st.columns([1,3])
with colA:
    st.subheader("Controls")
    if st.button("Initialize DB"):
        r = requests.post(f"{API_BASE}/init")
        st.success(r.json())

    limit = st.number_input("Fetch emails (limit)", min_value=1, max_value=500, value=50, step=5)
    if st.button("Fetch from IMAP"):
        with st.spinner("Fetching emails..."):
            r = requests.post(f"{API_BASE}/fetch_emails", json={"limit": int(limit)})
        st.success(r.json())

    st.markdown("---")
    st.subheader("Filters")
    order_by_priority = st.checkbox("Order by priority", value=True)
    only_support = st.checkbox("Only support emails", value=True)

with colB:
    st.subheader("Analytics (refresh)")
    if st.button("Refresh Analytics"):
        an = requests.get(f"{API_BASE}/analytics").json()
        st.write(an)
        # simple charts
        s1 = pd.Series(an.get("sentiment", {}))
        if not s1.empty:
            st.write("Sentiment distribution")
            fig = plt.figure()
            s1.plot(kind="bar")
            st.pyplot(fig)

        s2 = pd.Series(an.get("priority", {}))
        if not s2.empty:
            st.write("Priority distribution")
            fig2 = plt.figure()
            s2.plot(kind="bar")
            st.pyplot(fig2)

st.markdown("---")
st.subheader("📨 Inbox")

rows = requests.get(f"{API_BASE}/emails", params={"order_by_priority": str(order_by_priority).lower(), "only_support": str(only_support).lower()}).json()
df = pd.DataFrame(rows)
if df.empty:
    st.info("No emails to show. Fetch from IMAP or relax filters.")
else:
    st.dataframe(df[["id","sender","subject","received_at","sentiment","priority","status"]])

    sel = st.selectbox("Select email ID", options=df["id"].tolist())
    if sel:
        row = df[df["id"] == sel].iloc[0].to_dict()
        st.write("### Email Details")
        st.write(f"**From:** {row['sender']}  \n**Subject:** {row['subject']}  \n**Received:** {row['received_at']}")
        with st.expander("Body"):
            st.write(row["body"])

        st.write("**Extracted Info**")
        st.write({"phone": row.get("phone"), "alt_email": row.get("alt_email"), "summary": row.get("request_summary")})

        if st.button("Generate AI Draft Reply"):
            with st.spinner("Generating draft..."):
                r = requests.post(f"{API_BASE}/respond", json={"email_id": int(sel)})
            data = r.json()
            draft = data.get("draft","")
            st.session_state["draft"] = draft
            st.success("Draft generated! Scroll down to edit.")

        draft_text = st.text_area("Edit Draft", value=st.session_state.get("draft",""), height=220)
        if st.button("Send Reply (simulate)"):
            r = requests.post(f"{API_BASE}/send", json={"email_id": int(sel), "final": draft_text})
            if r.status_code == 200:
                st.success("Reply sent and marked as responded!")
            else:
                st.error(f"Error: {r.text}")
