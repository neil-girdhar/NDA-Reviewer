"""Generate a realistic test NDA .docx that is mostly Ascential-standard but contains
three deliberate flaws:
  - AMBER: Oral disclosures require 30-day written confirmation (acceptable fallback but
           weakens protection vs. Ascential's preferred 'whether or not marked' definition)
  - AMBER: Independent-development added as a 4th carve-out (Ascential's pure BPG/Titan
           form uses only three exceptions; this is an acceptable counterparty ask but
           removes the strongest protection)
  - RED:   Compelled-disclosure notice fixed at 14 days (impractical against fast-moving
           subpoenas; creates breach risk even when disclosure is legally compelled)
All other clauses mirror Ascential's BPG/Titan standard MNDA template language.
"""
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# ── Title ────────────────────────────────────────────────────────────────────
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("MUTUAL NON-DISCLOSURE AGREEMENT")
run.bold = True
run.font.size = Pt(14)

doc.add_paragraph()

# ── Parties preamble ─────────────────────────────────────────────────────────
doc.add_paragraph(
    "This Mutual Non-Disclosure Agreement (\"Agreement\") is entered into as of the date last "
    "signed below (the \"Effective Date\") by and between BPG Holdings IV Corp., a Delaware "
    "corporation, with offices at 975 Spaulding Avenue, Suite C, Ada, Michigan 49301 "
    "(\"Ascential\"), and Momentum Analytics Corp., a Delaware corporation, with offices at "
    "200 West Monroe Street, Suite 1400, Chicago, Illinois 60606 (\"Counterparty\"). "
    "Each party may act as a Disclosing Party and/or a Receiving Party under this Agreement. "
    "The parties wish to explore a potential commercial relationship (the \"Purpose\") and, "
    "in connection therewith, may exchange Confidential Information as defined below."
)

doc.add_paragraph()

# ── 1. Definitions ───────────────────────────────────────────────────────────
# GREEN: Broad CI definition mirroring Ascential's standard template;
#        includes existence of Agreement as CI; no marking required.
# AMBER: Oral disclosures require 30-day written confirmation — an acceptable fallback
#        Ascential has signed (e.g., IDEXX) but weaker than the preferred 'whether or
#        not marked' formulation.
doc.add_paragraph("1.  DEFINITIONS", style="Heading 2")
doc.add_paragraph(
    "1.1  \"Confidential Information\" means all confidential and/or proprietary information, "
    "including trade secrets, related in any way to the business or business plans, "
    "experiences or ideas of Disclosing Party and/or any of its subsidiaries and/or affiliates, "
    "and any of their respective shareholders, directors, members, managers, officers, "
    "employees, agents, and representatives, and their respective successors and assigns, "
    "as applicable (collectively, the \"Related Parties\"). The definition of Confidential "
    "Information is intended to be broad in scope and is not to be limited by the extent to "
    "which Disclosing Party or any Related Party uses or protects any particular information. "
    "Confidential Information includes the existence of this Agreement and the matters discussed "
    "in this Agreement, and the terms, conditions, status, and other facts related to the "
    "potential Purpose. Confidential Information may be disclosed in written, electronic, or "
    "other tangible form, or orally; provided, however, that oral disclosures shall constitute "
    "Confidential Information only if the Disclosing Party identifies them as confidential at "
    "the time of disclosure and confirms such designation in a written summary delivered to "
    "Receiving Party within thirty (30) days after such oral disclosure."
    # ^^^ AMBER FLAW: oral-confirmation requirement
)

doc.add_paragraph()

# AMBER + GREEN carve-outs
# GREEN: three standard Ascential carve-outs (publicly available, prior knowledge,
#        subsequent public availability)
# AMBER: fourth carve-out for independent development — acceptable fallback Ascential
#        has signed (AutoStore, SAP) but departs from the pure BPG/Titan three-exception form
doc.add_paragraph(
    "1.2  The only information disclosed by Disclosing Party or any Related Party to Receiving "
    "Party that does not constitute Confidential Information is: (i) information that is already "
    "publicly available at the time of disclosure; (ii) information that is already known to "
    "Receiving Party as of the date of this Agreement, as evidenced by prior documentation "
    "thereof; (iii) information that subsequently becomes publicly available through no default "
    "by Receiving Party of the terms of this Agreement, provided that such information shall be "
    "deemed Confidential Information until such time as it becomes publicly available; or "
    "(iv) information that is independently developed by Receiving Party without use or reference "
    "to the Confidential Information of Disclosing Party, as evidenced by contemporaneous "
    "written records. Receiving Party agrees that it will bear the burden of proving that any "
    "information is not Confidential Information pursuant to any exception in the preceding "
    "sentence."
    # ^^^ AMBER FLAW: independent-development carve-out (item iv)
    # GREEN: recipient burden-of-proof sentence preserved
)

doc.add_paragraph(
    "1.3  \"Representatives\" means each party's officers, directors, employees, attorneys, "
    "accountants, and financial advisors who need the information to perform their duties in "
    "connection with the Purpose."
)

doc.add_paragraph()

# ── 2. Term ──────────────────────────────────────────────────────────────────
# GREEN: 3-year agreement term with trade-secret perpetuity — matches Ascential's signed
#        range (Insight Direct, Sanmina 3-year post-termination tail).
doc.add_paragraph("2.  TERM", style="Heading 2")
doc.add_paragraph(
    "2.1  This Agreement shall commence on the Effective Date and shall remain in effect for "
    "three (3) years unless earlier terminated by either party upon thirty (30) days' prior "
    "written notice to the other. Termination of this Agreement shall not relieve either party "
    "of its obligations with respect to Confidential Information disclosed prior to the effective "
    "date of such termination. Notwithstanding the foregoing, obligations with respect to "
    "information that constitutes a trade secret under applicable law shall survive until such "
    "information no longer qualifies as a trade secret through no fault of Receiving Party."
)

doc.add_paragraph()

# ── 3. Confidentiality Obligations ───────────────────────────────────────────
# GREEN: strict-confidence standard; use limitation; Ascential's vicarious-liability language
doc.add_paragraph("3.  CONFIDENTIALITY OBLIGATIONS", style="Heading 2")
doc.add_paragraph(
    "3.1  Receiving Party shall hold all Confidential Information of Disclosing Party in strict "
    "confidence. Receiving Party shall not disclose any Confidential Information to any third "
    "party without the prior express written consent of Disclosing Party."
)
doc.add_paragraph(
    "3.2  Receiving Party shall use the Confidential Information solely for the Purpose and for "
    "no other purpose whatsoever. Reproduction of Confidential Information in any form requires "
    "the prior express written consent of Disclosing Party, which Receiving Party shall have "
    "the burden of proving was obtained."
)
doc.add_paragraph(
    "3.3  Receiving Party will only disclose the Confidential Information to those of its "
    "Representatives who need the information to perform their duties in connection with the "
    "Purpose. Receiving Party shall inform each such Representative of the confidential nature "
    "of the information and shall direct each such Representative to treat the information "
    "confidentially. Receiving Party shall be liable for all actions taken by any such "
    "Representative with respect to any Confidential Information."
    # GREEN: vicarious liability mirrors Ascential's standard template
)

doc.add_paragraph()

# ── 4. Permitted Disclosures ──────────────────────────────────────────────────
# RED: Compelled-disclosure notice fixed at 14 days — impractical against fast-moving
#      subpoenas; creates breach risk even when legally compelled (JLG red-flag pattern)
# GREEN (rest): cooperation, seek protective order — standard acceptable language
doc.add_paragraph("4.  PERMITTED DISCLOSURES", style="Heading 2")
doc.add_paragraph(
    "4.1  If Receiving Party becomes legally compelled to disclose any Confidential Information "
    "by a court, regulatory authority, or applicable law, Receiving Party shall provide "
    "Disclosing Party with written notice at least fourteen (14) days prior to making any such "
    "disclosure so that Disclosing Party may seek a protective order or other appropriate remedy. "
    "Receiving Party shall reasonably cooperate with Disclosing Party in connection with any "
    "such efforts. If a protective order or other remedy is not obtained, Receiving Party may "
    "disclose only that portion of the Confidential Information that it is legally required to "
    "disclose and shall use reasonable efforts to obtain assurances that confidential treatment "
    "will be accorded to such information."
    # ^^^ RED FLAW: fixed 14-day notice period (impractical against emergency orders)
)
doc.add_paragraph(
    "4.2  Defend Trade Secrets Act Notice. Notwithstanding any other provision of this Agreement, "
    "Receiving Party shall not be held criminally or civilly liable under any federal or state "
    "trade secret law for the disclosure of a trade secret that: (i) is made in confidence to a "
    "federal, state, or local government official, either directly or indirectly, or to an "
    "attorney, and solely for the purpose of reporting or investigating a suspected violation of "
    "law; or (ii) is made in a complaint or other document filed in a lawsuit or other "
    "proceeding, if such filing is made under seal."
    # GREEN: DTSA safe-harbor whistleblower carve-out — Ascential proactively includes this
)

doc.add_paragraph()

# ── 5. Return of Information ──────────────────────────────────────────────────
# GREEN: standard return/destroy clause with compliance-copy carve-out
doc.add_paragraph("5.  RETURN OF INFORMATION", style="Heading 2")
doc.add_paragraph(
    "5.1  Upon written request by Disclosing Party, or upon termination of this Agreement, "
    "Receiving Party shall promptly return or destroy all tangible materials containing "
    "Confidential Information and, upon request, shall certify in writing that it has done so. "
    "Receiving Party may retain one archival copy solely for legal compliance or regulatory "
    "purposes, which shall remain subject to the continuing confidentiality obligations of "
    "this Agreement."
)

doc.add_paragraph()

# ── 6. Intellectual Property ──────────────────────────────────────────────────
# GREEN: no IP transfer; third-party reports remain Discloser's property
doc.add_paragraph("6.  INTELLECTUAL PROPERTY", style="Heading 2")
doc.add_paragraph(
    "6.1  Nothing in this Agreement shall be construed as granting any rights by license or "
    "otherwise in or to any Confidential Information, or under any patent, copyright, trademark, "
    "or other intellectual property right of Disclosing Party."
)
doc.add_paragraph(
    "6.2  Any reports, analyses, or summaries prepared by or for Receiving Party that incorporate "
    "or are derived from Confidential Information of Disclosing Party shall be deemed the property "
    "of Disclosing Party and shall be subject to the terms of this Agreement."
    # GREEN: third-party reports deemed Discloser property — matches Ascential's standard
)

doc.add_paragraph()

# ── 7. Remedies ───────────────────────────────────────────────────────────────
# GREEN: mutual injunctive relief; no liquidated damages; no bond requirement
doc.add_paragraph("7.  REMEDIES", style="Heading 2")
doc.add_paragraph(
    "7.1  Each party acknowledges that any breach of this Agreement would cause irreparable harm "
    "to the other party for which monetary damages would be an inadequate remedy, and that the "
    "non-breaching party shall be entitled to seek injunctive or other equitable relief in any "
    "court of competent jurisdiction without the requirement to post bond or other security, and "
    "without the necessity of proving actual damages."
)
doc.add_paragraph(
    "7.2  The rights and remedies set out in this Agreement are in addition to, and not in lieu "
    "of, any other rights or remedies available at law or in equity."
)

doc.add_paragraph()

# ── 8. Governing Law ──────────────────────────────────────────────────────────
# GREEN: Michigan governing law — consistent with Ascential's Ada, MI headquarters
doc.add_paragraph("8.  GOVERNING LAW", style="Heading 2")
doc.add_paragraph(
    "8.1  This Agreement shall be governed by and construed in accordance with the laws of the "
    "State of Michigan, without regard to its conflict of law principles. Each party irrevocably "
    "consents to the exclusive jurisdiction of the state and federal courts located in Kent "
    "County, Michigan for the resolution of any dispute arising out of or relating to this "
    "Agreement."
)

doc.add_paragraph()

# ── 9. General Provisions ─────────────────────────────────────────────────────
# GREEN: standard boilerplate
doc.add_paragraph("9.  GENERAL PROVISIONS", style="Heading 2")
doc.add_paragraph(
    "9.1  Entire Agreement. This Agreement constitutes the entire agreement between the parties "
    "with respect to its subject matter and supersedes all prior negotiations, representations, "
    "warranties, and understandings of the parties with respect thereto."
)
doc.add_paragraph(
    "9.2  Amendments. No amendment or modification of this Agreement shall be valid unless made "
    "in writing and signed by duly authorized representatives of both parties."
)
doc.add_paragraph(
    "9.3  Severability. If any provision of this Agreement is held invalid or unenforceable by "
    "a court of competent jurisdiction, the remaining provisions shall continue in full force "
    "and effect."
)
doc.add_paragraph(
    "9.4  No Waiver. Failure to enforce any provision of this Agreement shall not constitute a "
    "waiver of that or any other provision."
)
doc.add_paragraph(
    "9.5  Assignment. Neither party may assign this Agreement or any of its rights or obligations "
    "hereunder without the prior written consent of the other party, except that either party "
    "may assign this Agreement without consent to an affiliate or in connection with a merger, "
    "acquisition, or sale of all or substantially all of its assets, provided that the assignee "
    "agrees in writing to be bound by the terms hereof."
)
doc.add_paragraph(
    "9.6  Counterparts. This Agreement may be executed in counterparts, each of which shall be "
    "deemed an original, and all of which together shall constitute one and the same instrument. "
    "Electronic signatures shall be deemed valid."
)

doc.add_paragraph()

# ── Signature block ───────────────────────────────────────────────────────────
doc.add_paragraph(
    "IN WITNESS WHEREOF, the parties have executed this Agreement as of the date last written below."
)
doc.add_paragraph()
doc.add_paragraph("BPG HOLDINGS IV CORP.                         MOMENTUM ANALYTICS CORP.")
doc.add_paragraph()
doc.add_paragraph("Signature: ____________________               Signature: ____________________")
doc.add_paragraph("Name:      ____________________               Name:      ____________________")
doc.add_paragraph("Title:     ____________________               Title:     ____________________")
doc.add_paragraph("Date:      ____________________               Date:      ____________________")

output_path = r"C:\Claude\Projects\NDA Reviewer\test_nda_momentum_analytics.docx"
doc.save(output_path)
print(f"Saved: {output_path}")
