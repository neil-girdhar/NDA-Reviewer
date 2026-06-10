from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# Title
title = doc.add_heading("NON-DISCLOSURE AGREEMENT", 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph("")

# Preamble
doc.add_paragraph(
    'This Non-Disclosure Agreement ("Agreement") is entered into as of the 1st day of June, 2026, '
    'between GlobalRetail Corp, a Delaware corporation with its principal place of business at '
    '100 Commerce Drive, New York, NY 10001 ("Disclosing Party" or "Client"), and Ascential MLS Limited, '
    'a company incorporated in England and Wales, with its registered office at 33 Kingsway, London WC2B 6UF '
    '("Receiving Party" or "Ascential").'
)

doc.add_paragraph(
    "WHEREAS, the Client desires to disclose certain confidential and proprietary information to Ascential "
    "for the purpose of evaluating a potential business relationship (the \"Purpose\");"
)

doc.add_paragraph(
    "NOW, THEREFORE, in consideration of the mutual covenants contained herein, the parties agree as follows:"
)

doc.add_paragraph("")

# Section 1 — Definition (RED: overly broad, no oral confirmation carve-out)
doc.add_heading("1. Definition of Confidential Information", level=1)
doc.add_paragraph(
    '"Confidential Information" means any and all information or data that has or could have commercial value '
    "or other utility in the business in which the Client is engaged. "
    "Confidential Information includes all business plans, financial data, customer lists, pricing strategies, "
    "product roadmaps, marketing strategies, technical specifications, trade secrets, and any other information "
    "disclosed by the Client, whether or not marked as confidential, and whether disclosed in written, oral, "
    "electronic, or any other form. For the avoidance of doubt, any information shared verbally shall be "
    "deemed Confidential Information regardless of whether it is subsequently confirmed in writing."
)

# Section 2 — Obligations (GREEN)
doc.add_heading("2. Obligations of Receiving Party", level=1)
doc.add_paragraph(
    "Ascential agrees to: (a) hold the Confidential Information in strict confidence and not to disclose it "
    "to any third party without the prior written consent of the Client; (b) use the Confidential Information "
    "solely for the Purpose and for no other purpose whatsoever; (c) restrict access to the Confidential "
    "Information to those of its employees, contractors, and agents who have a need to know such information "
    "and who are bound by confidentiality obligations no less restrictive than those contained herein; "
    "(d) protect the Confidential Information using the same degree of care it uses to protect its own "
    "most sensitive confidential information, but in no event less than reasonable care."
)

# Section 3 — Exclusions (RED: missing independent development and regulatory carve-outs)
doc.add_heading("3. Exclusions", level=1)
doc.add_paragraph(
    "The obligations of confidentiality set forth in this Agreement shall not apply to information that: "
    "(a) was already known to Ascential at the time of disclosure, provided Ascential can demonstrate such "
    "prior knowledge through contemporaneous written records; (b) becomes publicly known through no fault "
    "of Ascential. "
    "For the avoidance of doubt, there shall be no exclusion for information independently developed by "
    "Ascential without reference to the Confidential Information, and no exclusion for disclosures required "
    "by any regulatory authority or applicable law."
)

# Section 4 — Term (RED: perpetual)
doc.add_heading("4. Term", level=1)
doc.add_paragraph(
    "This Agreement shall commence on the date first written above and shall continue in perpetuity, "
    "unless terminated by the Client upon thirty (30) days written notice to Ascential. "
    "Notwithstanding any termination of this Agreement, Ascential's obligations with respect to "
    "Confidential Information disclosed prior to termination shall survive and continue forever "
    "without limitation."
)

# Section 5 — Remedies (AMBER: one-sided injunctive relief, attorneys fees)
doc.add_heading("5. Remedies", level=1)
doc.add_paragraph(
    "Ascential acknowledges that any breach of this Agreement may cause irreparable harm to the Client "
    "for which monetary damages would be an inadequate remedy. Accordingly, in the event of any actual "
    "or threatened breach, the Client shall be entitled to seek equitable relief, including injunctive "
    "relief and specific performance, without the requirement of posting a bond or other security and "
    "without proof of actual damages, in addition to all other remedies available at law or in equity. "
    "Ascential shall reimburse the Client for all costs and expenses, including reasonable attorneys' "
    "fees, incurred in connection with enforcing this Agreement."
)

# Section 6 — Liquidated Damages (RED)
doc.add_heading("6. Liquidated Damages", level=1)
doc.add_paragraph(
    "In the event of a breach of this Agreement by Ascential, Ascential shall pay to the Client "
    "liquidated damages in the amount of £500,000 per incident of disclosure, which the parties "
    "acknowledge represents a reasonable pre-estimate of the loss likely to be suffered by the Client. "
    "Payment of liquidated damages shall not limit the Client's right to seek additional damages "
    "or other remedies available at law or in equity."
)

# Section 7 — Return of Information (AMBER)
doc.add_heading("7. Return or Destruction of Information", level=1)
doc.add_paragraph(
    "Upon request by the Client at any time, or upon termination of this Agreement, Ascential shall "
    "promptly return or destroy all Confidential Information and any copies thereof, including all "
    "electronic copies and derivative works incorporating Confidential Information. Ascential shall "
    "certify in writing within five (5) business days that all such materials have been returned or "
    "destroyed. Notwithstanding the foregoing, Ascential may retain one archival copy of the "
    "Confidential Information solely for the purpose of establishing the scope of its obligations "
    "under this Agreement."
)

# Section 8 — No Licence (GREEN)
doc.add_heading("8. No Licence", level=1)
doc.add_paragraph(
    "Nothing in this Agreement shall be construed as granting any rights, by licence or otherwise, "
    "to any Confidential Information, or to any invention or any patent, copyright, trademark, or "
    "other intellectual property right of the Client. All Confidential Information shall remain the "
    "sole and exclusive property of the Client."
)

# Section 9 — Assignment (RED: can assign to Ascential competitors)
doc.add_heading("9. Assignment", level=1)
doc.add_paragraph(
    "The Client may assign this Agreement and all of its rights hereunder to any successor entity "
    "or acquirer of all or substantially all of the Client's business or assets, including any "
    "competitor of Ascential, without the prior written consent of Ascential. Ascential may not "
    "assign this Agreement or any of its rights or obligations hereunder without the prior written "
    "consent of the Client. Any purported assignment in violation of this Section shall be null and void."
)

# Section 10 — Governing Law (AMBER: New York only, Ascential waives inconvenient forum)
doc.add_heading("10. Governing Law and Jurisdiction", level=1)
doc.add_paragraph(
    "This Agreement shall be governed by and construed in accordance with the laws of the State of "
    "New York, without regard to its conflict of laws principles. Each party irrevocably submits to "
    "the exclusive jurisdiction of the courts located in New York County, New York for any dispute "
    "arising out of or relating to this Agreement. Ascential waives any objection to the laying of "
    "venue of any such proceedings in New York County and waives any objection that such courts are "
    "an inconvenient forum."
)

# Section 11 — Entire Agreement (GREEN)
doc.add_heading("11. Entire Agreement", level=1)
doc.add_paragraph(
    "This Agreement constitutes the entire agreement between the parties with respect to the subject "
    "matter hereof and supersedes all prior and contemporaneous agreements, understandings, negotiations, "
    "and discussions, whether oral or written, of the parties with respect to the subject matter hereof. "
    "This Agreement may not be amended or modified except by a written instrument signed by both parties."
)

# Section 12 — Severability (GREEN)
doc.add_heading("12. Severability", level=1)
doc.add_paragraph(
    "If any provision of this Agreement is found to be invalid, illegal, or unenforceable, the remaining "
    "provisions shall continue in full force and effect, and the invalid, illegal, or unenforceable "
    "provision shall be modified to the minimum extent necessary to make it valid, legal, and enforceable."
)

# Signatures
doc.add_paragraph("")
doc.add_paragraph(
    "IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above."
)
doc.add_paragraph("")

table = doc.add_table(rows=4, cols=2)
table.cell(0, 0).text = "GLOBALRETAIL CORP"
table.cell(0, 1).text = "ASCENTIAL MLS LIMITED"
table.cell(1, 0).text = "Signature: _________________________"
table.cell(1, 1).text = "Signature: _________________________"
table.cell(2, 0).text = "Name: _____________________________"
table.cell(2, 1).text = "Name: _____________________________"
table.cell(3, 0).text = "Title: ______________________________"
table.cell(3, 1).text = "Title: ______________________________"

doc.save("sample_nda.docx")
print("sample_nda.docx created successfully")
