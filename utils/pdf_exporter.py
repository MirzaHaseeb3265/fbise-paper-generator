from __future__ import annotations
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.units import mm
from xml.sax.saxutils import escape

def build_pdf(paper,s):
    b=BytesIO(); doc=SimpleDocTemplate(b,pagesize=A4,rightMargin=12*mm,leftMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    styles=getSampleStyleSheet(); normal=ParagraphStyle('Compact',parent=styles['BodyText'],fontName='Helvetica',fontSize=9,leading=10,spaceAfter=2)
    head=ParagraphStyle('Head',parent=normal,fontName='Helvetica-Bold',alignment=TA_CENTER,fontSize=10,leading=11,spaceBefore=3,spaceAfter=3)
    story=[]
    title="Physics HSC-I - FLP" if s['paper_type']=="FLP Paper" and s['level']=="HSSC-I" else ("Physics HSC-II - FLP" if s['paper_type']=="FLP Paper" else f"{s['level']} PHYSICS (FEDERAL)")
    story += [Paragraph(escape(title),head),Paragraph(escape("Topics: "+", ".join(s['chapters'])),head)]
    story.append(Paragraph("SECTION-A (OBJECTIVE)" if s['paper_type']=="FLP Paper" else f"Encircle the right answer ({len(paper['mcqs'])*s['mcq_marks']} Marks)",head))
    for i,q in enumerate(paper['mcqs'],1):
        o=q['options']; block=[Paragraph(escape(f"{i}. {q['question']}"),normal),Paragraph(escape(f"A. {o['A']}    B. {o['B']}    C. {o['C']}    D. {o['D']}"),normal)]
        story.append(KeepTogether(block))
    story.append(Paragraph("SECTION-B (SHORT QUESTIONS)" if s['paper_type']=="FLP Paper" else "Short Questions",head))
    for i,q in enumerate(paper['short_questions'],1):
        block=[Paragraph(escape(f"{i}. {q['question']}"),normal)]
        if q.get('or_question'): block += [Paragraph("<b>OR</b>",head),Paragraph(escape(q['or_question']),normal)]
        story.append(KeepTogether(block))
    story.append(Paragraph("SECTION-C (LONG QUESTIONS)" if s['paper_type']=="FLP Paper" else "Long Questions",head))
    for i,q in enumerate(paper['long_questions'],1):
        block=[Paragraph(escape(f"{i}. {q['question']}"),normal)]
        if q.get('or_question'): block += [Paragraph("<b>OR</b>",head),Paragraph(escape(q['or_question']),normal)]
        story.append(KeepTogether(block))
    doc.build(story); return b.getvalue()
