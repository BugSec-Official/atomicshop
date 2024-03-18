# This was done for Flask endpoint.
import io

from flask import request, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


def some_function_to_get_file_data(file):
    print(file)
    return {}


def report():
    """
    The function generates a PDF file Report and returns the PDF file.
    :return:
    """

    # Extract query parameters or set default values
    file = request.args.get('file', default=None, type=str)

    # Get the data.
    file_data: dict = some_function_to_get_file_data(file)

    if 'file_name' in file_data:
        download_name = f"report_{file_data['file_name']}.pdf"
    else:
        raise ValueError("The file data does not contain a 'file_name'.")

    # Create the report.
    pdf_io = _create_pdf_io_and_report(file_data)

    # Return the PDF file as a response.
    return send_file(pdf_io, as_attachment=True, download_name=download_name, mimetype='application/pdf')


def _create_pdf_io_and_report(file_data: dict):
    """
    The function creates a PDF report and returns the PDF file.
    :param file_data: dict, the file data.
    :return:
    """

    # create a PDF file in memory
    pdf_io = io.BytesIO()

    # Create the report to 'pdf_io' file object.
    _create_report(file_data, pdf_io)

    # Make sure to seek to the start of the BytesIO object
    pdf_io.seek(0)

    # # Save the PDF file to disk
    # with open(file_name, "wb") as f:
    #     f.write(pdf_io.read())

    # Return the PDF file
    return pdf_io


def _create_report(file_data: dict, file_object):
    """
    The function creates a PDF report.
    :param file_data: dict, the file data.
    :return:
    """

    doc = SimpleDocTemplate(file_object, pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []

    # Define a custom style for the title
    title_style = ParagraphStyle(
        name='CenteredTitle',
        parent=styles['Heading1'],  # Inherit from Heading1 style
        alignment=TA_CENTER,  # Center-align the text
        fontSize=18,  # Customize the font size
        spaceAfter=20,  # Add some space after the title for separation
    )

    normal_style = styles['Normal']
    heading_style = styles['Heading1']

    # Add the title
    flowables.append(Paragraph(f"Report: {file_data['Name']}", title_style))

    # Add a spacer if needed (optional, depending on your layout)
    flowables.append(Spacer(1, 12))

    # Add a heading
    flowables.append(Paragraph("Info", heading_style))
    flowables.append(Spacer(1, 12))  # Add some space after the heading

    # Iterate over data to add it as paragraphs
    for key, value in file_data.items():
        flowables.append(Paragraph(f"<b>{key}:</b> {value}", normal_style))
        flowables.append(Spacer(1, 12))  # Add space between items for readability

    # Add a heading
    flowables.append(Paragraph("Analysis", heading_style))
    flowables.append(Spacer(1, 12))

    for key, value in file_data['analysis'].items():
        if value['color'] == 'warning':
            value_text = f"<font color='yellow'>{value['file_count']}</font>"
        elif value['color'] == 'danger':
            value_text = f"<font color='red'>{value['file_count']}</font>"
        else:
            value_text = value['file_count']

        flowables.append(Paragraph(f"<b>{key}:</b> {value_text}", normal_style))
        flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)
