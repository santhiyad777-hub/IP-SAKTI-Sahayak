"""Optional SIH workflows; legal decisions remain in the grounded answer path."""
import json
from pathlib import Path
import streamlit as st
from security.downloads import private_download
from utils.workspace_tools import PROFILE_FIELDS, profile_prompt, evidence_passport, review_pack, source_inventory, record_event


def workflow_panel(chat, jurisdiction, root, t, persist, private_root=None):
    private_root = private_root or root
    with st.expander(t("Product brief & review tools"), expanded=False):
        product, library, expert, privacy = st.tabs([t("Product brief"), t("Source freshness"), t("Expert review"), t("Privacy & audit")])
        with product:
            st.caption(t("Save product facts once. Ask for classification or an ABS review using the same facts."))
            profile = chat.get("product_profile", {})
            with st.form("product_brief_" + chat["id"]):
                fields = {}
                columns = st.columns(2)
                for index, (key, label) in enumerate(PROFILE_FIELDS.items()):
                    fields[key] = columns[index % 2].text_input(t(label), value=profile.get(key, ""), max_chars=2000, key=f"profile_{chat['id']}_{key}")
                save, classify, abs_review = st.columns(3)
                save_only = save.form_submit_button(t("Save brief"), width="stretch")
                classify_now = classify.form_submit_button(t("Check classification"), width="stretch")
                abs_now = abs_review.form_submit_button(t("Review ABS"), width="stretch")
            if save_only or classify_now or abs_now:
                chat["product_profile"] = fields
                profile = fields
                persist()
                try:
                    record_event(Path(private_root) / "knowledge_base/audit.jsonl", "profile_saved")
                except OSError:
                    st.warning(t("The brief was saved, but the audit event could not be recorded."))
                if save_only:
                    st.success(t("Product brief saved to this conversation."))
                else:
                    st.session_state.regenerate_question = profile_prompt(fields, "abs" if abs_now else "classification")
                    st.session_state.smart_cache = {}
            missing = [t(label) for key, label in PROFILE_FIELDS.items() if not profile.get(key, "").strip()]
            if missing:
                st.caption(t("Not supplied") + ": " + ", ".join(missing))
            st.caption(t("Leave unknown facts blank. These are user-supplied facts, not an approval or a legal classification."))
        with library:
            inventory = source_inventory(root, jurisdiction)
            st.caption(t("Only the selected jurisdiction is shown. Download age does not establish legal currency."))
            search = st.text_input(t("Find a source"), key="source_freshness_search")
            visible = [row for row in inventory if search.lower() in (row["Title"] + " " + row["Regime"]).lower()]
            if visible:
                st.dataframe(visible, hide_index=True, width="stretch",
                    column_config={"Official URL": st.column_config.LinkColumn(t("Official URL"))})
                private_download(t("Download source inventory"), json.dumps(visible, ensure_ascii=False, indent=2), "source-inventory.json", "application/json", on_click="ignore")
            else:
                st.info(t("No matching sources in the local manifest."))
            st.caption(t("Corpus refresh is an administrator-reviewed operation. This view does not fetch or silently update laws."))
        with expert:
            st.write(t("Prepare your questions, product facts and cited answers for a human IP facilitator."))
            st.link_button(t("Find a WIPO TISC facilitator"), "https://www.wipo.int/en/web/tisc")
            private_download(t("Download expert review pack"), review_pack(chat), "IP-SAKTI-expert-review.md", "text/markdown", on_click="ignore")
            st.caption(t("Review confidential details before sharing. Nothing is sent to a facilitator automatically."))
        with privacy:
            st.caption("Your history, documents, briefs and audit export belong to your signed-in account. Service operators can access server storage.")
            st.write(t("Questions and relevant source excerpts are sent to the configured AI provider. Translation may use Bhashini. Chats, product briefs and uploads are stored locally."))
            st.caption(t("Use the conversation and document delete controls to remove local items. Exports, backups and provider-side retention are separate."))
            st.caption(t("The local audit records event type, time, jurisdiction and evidence counts. It excludes question text, answers, product facts and credentials."))
            st.caption(t("Paid-source connectors are disabled. No subscription access is performed."))
            audit_path = Path(private_root) / "knowledge_base/audit.jsonl"
            if audit_path.is_file():
                private_download(t("Download local audit"), audit_path.read_bytes(), "audit.jsonl", "application/x-ndjson", on_click="ignore")


def passport_panel(message, t):
    passport = evidence_passport(message)
    st.caption(t(passport["status"]) + " | " + t("Evidence indicator, not a legal confidence score"))
    if not passport["sources"] and not passport["unresolved_references"]:
        return
    with st.expander(t("Evidence passport")):
        st.caption(t("References below occur in this answer. Excerpts are retrieved context, not independent verification of every claim."))
        for source in passport["sources"]:
            st.markdown(f"**[{source['reference']}] {source['title']}**")
            if source["url"].startswith("https://"):
                st.link_button(t("Open original source"), source["url"], width="content")
            st.caption(f"{source['jurisdiction']} | {source['regime']} | " + t("Retrieved") + f": {source['retrieved_at']}")
            st.caption(t("Version") + ": " + source["version"])
            if source["pdf_page"]:
                st.caption(t("PDF page") + f": {source['pdf_page']}")
            st.text(source["excerpt"][:2400])
        if passport["unresolved_references"]:
            st.warning(t("Some references cannot be matched to stored evidence. Request a new answer or human review."))
        private_download(t("Download evidence passport"), json.dumps(passport, ensure_ascii=False, indent=2),
                           "evidence-passport.json", "application/json", key="passport_" + message["message_id"], on_click="ignore")
