import streamlit as st
import pandas as pd
import io
import time
import threading
from email_engine import (
    find_email_from_phone_and_name,
    generate_email_permutations,
    bulk_find_emails,
    get_mx_record,
    verify_email_smtp,
)

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Email Finder Bot — Phone & Name to Email",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Dark page background */
.stApp { background: #0d1117; }

/* Header */
.main-title {
    font-size: 2.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 50%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.2;
    margin-bottom: 0.3rem;
}
.main-subtitle {
    color: #6B7280;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

/* Cards */
.stat-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.9) 0%, rgba(15,23,42,0.9) 100%);
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 14px;
    padding: 1.2rem 1rem;
    text-align: center;
    transition: border-color 0.3s;
}
.stat-card:hover { border-color: rgba(139,92,246,0.5); }
.stat-label {
    color: #6B7280;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
}
.stat-value {
    color: #F1F5F9;
    font-size: 1.4rem;
    font-weight: 700;
    word-break: break-all;
}

/* Email result items */
.email-verified {
    display: inline-block;
    background: rgba(16,185,129,0.15);
    border: 1px solid rgba(16,185,129,0.4);
    border-radius: 8px;
    padding: 0.35rem 0.75rem;
    font-size: 0.9rem;
    color: #6EE7B7;
    font-family: 'Courier New', monospace;
    margin: 0.2rem 0;
}
.email-uncertain {
    display: inline-block;
    background: rgba(245,158,11,0.12);
    border: 1px solid rgba(245,158,11,0.35);
    border-radius: 8px;
    padding: 0.35rem 0.75rem;
    font-size: 0.9rem;
    color: #FCD34D;
    font-family: 'Courier New', monospace;
    margin: 0.2rem 0;
}
.email-found {
    display: inline-block;
    background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.35);
    border-radius: 8px;
    padding: 0.35rem 0.75rem;
    font-size: 0.9rem;
    color: #93C5FD;
    font-family: 'Courier New', monospace;
    margin: 0.2rem 0;
}
.email-candidate {
    display: inline-block;
    background: rgba(107,114,128,0.12);
    border: 1px solid rgba(107,114,128,0.3);
    border-radius: 8px;
    padding: 0.3rem 0.65rem;
    font-size: 0.85rem;
    color: #9CA3AF;
    font-family: 'Courier New', monospace;
    margin: 0.15rem 0;
}

/* Badge */
.badge {
    display: inline-block;
    background: rgba(139,92,246,0.2);
    color: #A78BFA;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.15rem 0.6rem;
    margin-left: 0.4rem;
    vertical-align: middle;
}
.badge-green {
    background: rgba(16,185,129,0.2);
    color: #34D399;
}
.badge-yellow {
    background: rgba(245,158,11,0.2);
    color: #FCD34D;
}

/* Progress log */
.log-box {
    background: #0a0e1a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    font-family: 'Courier New', monospace;
    font-size: 0.82rem;
    color: #64748B;
    max-height: 220px;
    overflow-y: auto;
}

/* Divider */
.section-divider {
    border: none;
    border-top: 1px solid #1e293b;
    margin: 1.2rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## ⚙️ Settings")
st.sidebar.markdown("---")

target_domains_selected = st.sidebar.multiselect(
    "🎯 Target Email Domains",
    options=["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com", "icloud.com"],
    default=["gmail.com", "yahoo.com", "outlook.com"],
)
custom_domain = st.sidebar.text_input("➕ Add Custom Domain (optional):", placeholder="company.com")
if custom_domain.strip():
    target_domains_selected.append(custom_domain.strip())

if not target_domains_selected:
    target_domains_selected = ["gmail.com", "yahoo.com", "outlook.com"]

do_smtp = st.sidebar.toggle("✅ SMTP Email Verification", value=True,
                             help="SMTP দিয়ে email টা সত্যিই exist করে কিনা verify করবে")
st.sidebar.markdown("---")
st.sidebar.info(
    "**কিভাবে কাজ করে?**\n\n"
    "1. 📞 **Phone → Name:** Web OSINT দিয়ে number থেকে নাম বের করে\n"
    "2. 🔮 **Name → Emails:** সব সম্ভাব্য email format তৈরি করে\n"
    "3. ✅ **SMTP Verify:** প্রতিটি email SMTP দিয়ে check করে\n"
    "4. 🌐 **Direct Dork:** `\"number\" @gmail.com` style search করে সরাসরি email খোঁজে"
)


# ─── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">⚡ Phone & Name → Email Finder</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Phone number বা ব্যক্তির নাম দিয়ে রেজিস্টার্ড ইমেইল অ্যাড্রেস বের করুন — SMTP Verified & Web OSINT Powered</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎯 Real Phone & Name Email Finder", "📖 System Guide"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Single Finder
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### ফোন নাম্বার এবং/অথবা নাম দিয়ে ইমেইল খুঁজুন")

    col_n, col_p = st.columns(2)
    with col_n:
        inp_name = st.text_input(
            "👤 ব্যক্তির নাম (Name):",
            placeholder="e.g. Maksudur Rahman",
            help="নাম দিলে email permutation বেশি accurate হয়"
        )
    with col_p:
        inp_phone = st.text_input(
            "📱 ফোন নাম্বার (Phone):",
            placeholder="e.g. 01315906086",
            help="যেকোনো format এ দিতে পারেন"
        )

    st.caption("💡 নাম + ফোন নাম্বার দুটো একসাথে দিলে সবচেয়ে accurate রেজাল্ট আসবে।")

    search_btn = st.button("🚀 Find Email Address", type="primary", use_container_width=True)

    if search_btn:
        if not inp_name.strip() and not inp_phone.strip():
            st.warning("⚠️ অনুগ্রহ করে নাম অথবা ফোন নাম্বার দিন।")
        else:
            log_lines = []
            log_box = st.empty()
            spinner_text = st.empty()

            def update_log(step, detail=""):
                entry = f"{step}: {detail}" if detail else step
                log_lines.append(entry)
                log_content = "\n".join(log_lines[-12:])
                log_box.markdown(f'<div class="log-box">{log_content}</div>', unsafe_allow_html=True)

            update_log("🚀 Starting", "Initializing search engine...")

            start = time.time()
            result = find_email_from_phone_and_name(
                phone=inp_phone.strip(),
                name=inp_name.strip(),
                target_domains=list(target_domains_selected),
                do_smtp_verify=do_smtp,
                progress_callback=update_log,
            )
            elapsed = round(time.time() - start, 2)
            log_box.empty()

            # ── Summary Cards ──────────────────────────────────────────────────
            st.success(f"✅ Search completed in **{elapsed}s**")

            phone_info = result.get("phone_info", {})
            resolved_name = result.get("resolved_name", "")
            smtp_v = result.get("smtp_verified", [])
            smtp_u = result.get("smtp_uncertain", [])
            direct = result.get("directly_found_emails", [])
            candidates = result.get("email_candidates", [])
            primary = result.get("primary_email", "Not Found")
            google_status = result.get("google_recovery_status", "Not Run")

            if not resolved_name and primary == "Not Found" and not direct and not smtp_v:
                st.warning("⚠️ এই ফোন নাম্বারের জন্য ইন্টারনেটে বা সোশ্যাল মিডিয়ায় কোনো রেজিস্টার্ড নাম বা ইমেইল পাওয়া যায়নি (No Profile / Email Found)।")

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'''<div class="stat-card">
                    <div class="stat-label">Resolved Name</div>
                    <div class="stat-value" style="font-size:1.1rem; color:#A5B4FC;">{resolved_name or "—"}</div>
                    <div style="font-size:0.75rem; color:#FBBF24; margin-top:4px;">{google_status}</div>
                </div>''', unsafe_allow_html=True)
            with c2:
                st.markdown(f'''<div class="stat-card">
                    <div class="stat-label">Primary Email</div>
                    <div class="stat-value" style="font-size:0.95rem; color:#6EE7B7;">{primary}</div>
                </div>''', unsafe_allow_html=True)
            with c3:
                st.markdown(f'''<div class="stat-card">
                    <div class="stat-label">SMTP Verified ✅</div>
                    <div class="stat-value" style="color:#34D399;">{len(smtp_v)}</div>
                </div>''', unsafe_allow_html=True)
            with c4:
                st.markdown(f'''<div class="stat-card">
                    <div class="stat-label">Total Emails</div>
                    <div class="stat-value" style="color:#F472B6;">{len(result.get("all_emails_ranked", []))}</div>
                </div>''', unsafe_allow_html=True)

            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

            col_l, col_r = st.columns(2)

            with col_l:
                with st.expander("✅ SMTP Verified Emails (সবচেয়ে নির্ভরযোগ্য)", expanded=True):
                    if smtp_v:
                        for item in smtp_v:
                            st.markdown(f'<div class="email-verified">✅ {item["email"]}</div><br>', unsafe_allow_html=True)
                            st.caption(f'Reason: {item["reason"]}')
                    else:
                        st.info("কোনো email SMTP দিয়ে fully verify হয়নি (বেশিরভাগ provider port 25 block করে)।")

                with st.expander("🌐 Directly Found from Web (OSINT)", expanded=True):
                    if direct:
                        for e in direct:
                            st.markdown(f'<div class="email-found">🌐 {e}</div><br>', unsafe_allow_html=True)
                    else:
                        st.info("Web search থেকে সরাসরি কোনো email পাওয়া যায়নি।")

            with col_r:
                with st.expander("🔮 SMTP Uncertain (Server blocked check)", expanded=True):
                    if smtp_u:
                        for item in smtp_u[:15]:
                            st.markdown(f'<div class="email-uncertain">❓ {item["email"]}</div><br>', unsafe_allow_html=True)
                            st.caption(f'Reason: {item["reason"]}')
                    else:
                        st.info("কোনো uncertain email নেই।")

                with st.expander(f"📋 All Permutation Candidates ({len(candidates)} টি)", expanded=False):
                    if candidates:
                        for c in candidates:
                            st.markdown(f'<div class="email-candidate">{c}</div><br>', unsafe_allow_html=True)

            # ── Phone Info ─────────────────────────────────────────────────────
            if phone_info:
                st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
                with st.expander("📱 Phone Number Details"):
                    pi_c1, pi_c2, pi_c3 = st.columns(3)
                    with pi_c1:
                        st.metric("E.164 Format", phone_info.get("e164", "—"))
                        st.metric("Country", phone_info.get("country", "—"))
                    with pi_c2:
                        st.metric("National Format", phone_info.get("national", "—"))
                        st.metric("Carrier", phone_info.get("carrier", "—"))
                    with pi_c3:
                        st.metric("Region Code", phone_info.get("region", "—"))
                        st.metric("Valid Number", "✅ Yes" if phone_info.get("valid") else "❌ No")

            # ── Download Results ───────────────────────────────────────────────
            all_emails = result.get("all_emails_ranked", [])
            if all_emails:
                st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
                dl_df = pd.DataFrame({
                    "Email": all_emails,
                    "Status": [
                        "SMTP Verified" if any(item["email"] == e for item in smtp_v)
                        else "Directly Found" if e in direct
                        else "SMTP Uncertain" if any(item["email"] == e for item in smtp_u)
                        else "Candidate"
                        for e in all_emails
                    ]
                })
                csv_bytes = dl_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Results as CSV",
                    data=csv_bytes,
                    file_name=f"email_results_{inp_phone or inp_name}.csv",
                    mime="text/csv",
                    use_container_width=True
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Bulk Finder
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### একসাথে অনেক নাম্বার / নামের ইমেইল খুঁজুন")

    input_mode = st.radio(
        "ইনপুট পদ্ধতি:",
        ["📝 Paste করুন", "📤 ফাইল আপলোড করুন (CSV/Excel/TXT)"],
        horizontal=True
    )

    phone_list_bulk = []
    name_list_bulk = []

    if input_mode == "📝 Paste করুন":
        col_pb, col_nb = st.columns(2)
        with col_pb:
            raw_phones = st.text_area(
                "📱 Phone Numbers (প্রতি লাইনে ১টি):",
                height=160,
                placeholder="01712345678\n01812345678\n01912345678"
            )
            if raw_phones.strip():
                phone_list_bulk = [l.strip() for l in raw_phones.splitlines() if l.strip()]
        with col_nb:
            raw_names = st.text_area(
                "👤 Names (optional, same order):",
                height=160,
                placeholder="Maksudur Rahman\nKarim Mia\n..."
            )
            if raw_names.strip():
                name_list_bulk = [l.strip() for l in raw_names.splitlines() if l.strip()]
    else:
        uploaded = st.file_uploader("CSV, Excel বা TXT আপলোড করুন", type=["csv", "xlsx", "txt"])
        if uploaded:
            try:
                if uploaded.name.endswith(".csv"):
                    df_up = pd.read_csv(uploaded)
                elif uploaded.name.endswith(".xlsx"):
                    df_up = pd.read_excel(uploaded)
                else:
                    content = uploaded.read().decode("utf-8")
                    phone_list_bulk = [l.strip() for l in content.splitlines() if l.strip()]
                    df_up = None

                if 'df_up' in dir() and df_up is not None:
                    st.dataframe(df_up.head(), use_container_width=True)
                    all_cols = list(df_up.columns)
                    phone_col = st.selectbox("📱 Phone column:", all_cols)
                    name_col = st.selectbox("👤 Name column (optional):", ["— None —"] + all_cols)
                    phone_list_bulk = df_up[phone_col].dropna().astype(str).tolist()
                    if name_col != "— None —":
                        name_list_bulk = df_up[name_col].dropna().astype(str).tolist()
            except Exception as ex:
                st.error(f"ফাইল পড়তে সমস্যা: {ex}")

    if phone_list_bulk:
        st.info(f"📊 মোট **{len(phone_list_bulk)}** টি entry প্রস্তুত।")
        if st.button("🚀 Start Bulk Email Lookup", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_txt = st.empty()

            def bulk_cb(current, total):
                pct = int(current / total * 100)
                progress_bar.progress(pct)
                status_txt.markdown(f"**Progress:** {current}/{total} ({pct}%)")

            t0 = time.time()
            bulk_results = bulk_find_emails(
                phone_list=phone_list_bulk,
                name_list=name_list_bulk if name_list_bulk else None,
                target_domains=list(target_domains_selected),
                do_smtp_verify=do_smtp,
                callback=bulk_cb,
            )
            elapsed_b = round(time.time() - t0, 2)
            status_txt.success(f"✅ Completed {len(phone_list_bulk)} records in {elapsed_b}s!")

            # Build output table
            rows = []
            for r in bulk_results:
                ph_info = r.get("phone_info", {})
                rows.append({
                    "Input Phone": r.get("input_phone", ""),
                    "Input Name": r.get("input_name", ""),
                    "Resolved Name": r.get("resolved_name", ""),
                    "Primary Email": r.get("primary_email", "Not Found"),
                    "SMTP Verified Emails": " | ".join(x["email"] for x in r.get("smtp_verified", [])) or "None",
                    "Directly Found": " | ".join(r.get("directly_found_emails", [])) or "None",
                    "All Candidates": " | ".join(r.get("email_candidates", [])[:5]) or "None",
                    "Country": ph_info.get("country", ""),
                    "Carrier": ph_info.get("carrier", ""),
                })

            out_df = pd.DataFrame(rows)
            st.markdown("### 📋 Results")
            st.dataframe(out_df, use_container_width=True)

            # Downloads
            bc1, bc2 = st.columns(2)
            with bc1:
                csv_d = out_df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download CSV", data=csv_d,
                                   file_name="bulk_email_results.csv", mime="text/csv",
                                   use_container_width=True)
            with bc2:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    out_df.to_excel(w, index=False, sheet_name="Results")
                st.download_button("📥 Download Excel", data=buf.getvalue(),
                                   file_name="bulk_email_results.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — System Guide
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("""
### 📖 কিভাবে সবচেয়ে Accurate রেজাল্ট পাবেন?

#### 🥇 ১. Phone Number সার্চ:
- ফোন নাম্বারটি ইনপুট দিলে বট স্বয়ংক্রিয়ভাবে:
  1. সোশ্যাল মিডিয়া (WhatsApp, Truecaller, Facebook) থেকে **অরিজিনাল প্রোফাইল নাম (First & Last Name)** এক্সট্রাক্ট করে।
  2. গুগলের অফিশিয়াল **Google Account Recovery ('Find Your Email')** ইঞ্জিনে নাম যাচাই করে ১০০% রিয়েল রেজিস্টার্ড ইমেইল আবিষ্কার করে।
  3. সরাসরি SMTP মেলবক্স সকেট হ্যান্ডশেক সম্পন্ন করে আসল ইমেইল নিশ্চিত করে।

#### 🥈 ২. Name + Phone একসাথে দিলে:
- নাম ও ফোন দুটো একসাথে ইনপুট দিলে সিস্টেমটি সোশ্যাল এক্সট্রাকশনের পাশাপাশি সরাসরি গুগল অ্যাকাউন্ট রিকভারি নেম ভ্যালিডেশন চালায়।

---

### ⚠️ যদি কোনো তথ্য পাওয়া না যায় (No Result Found):
- যে নাম্বারের বিপরীতে কোনো তথ্য বা ইমেইল ইন্টারনেটে ইনডেক্স করা নেই, তার ক্ষেত্রে সিস্টেমটি পরিষ্কারভাবে **"Not Found"** বার্তা দেখাবে — কোনো ভুয়া বা কাল্পনিক ইমেইল জেনারেট করবে না।

---

### ✅ SMTP Verification কী?
**SMTP** (Simple Mail Transfer Protocol) দিয়ে মেলবক্স সার্ভারে সরাসরি কোয়েরি করা হয় যে ইমেইল ঠিকানাটি সক্রিয় এবং গ্রহণযোগ কিনা।
- ✅ **Verified:** সার্ভার নিশ্চিত করেছে যে ইমেইলটি শতভাগ চালু রয়েছে।
- ❓ **Uncertain:** নেটওয়ার্ক বা ISP পোর্ট ২৫ ব্লক করলে মেলবক্স অস্তিত্ব যাচাই পেন্ডিং থাকে।
    """)
