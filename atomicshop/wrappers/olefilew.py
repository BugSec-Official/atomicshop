import os
import datetime
import json

import olefile


def convert_object_to_string(obj):
    if isinstance(obj, bytes):
        # MSI Database uses latin-1 encoding for strings, could be that other ole files too.
        return obj.decode('latin-1')
    elif isinstance(obj, datetime.datetime):
        return obj.strftime('%Y-%m-%d-%H:%M:%S')
    return obj


def extract_ole_metadata(ole_file_path: str, output_directory: str):
    """
    Extract metadata from an OLE2 file.
    :param ole_file_path:
    :param output_directory:
    :return:
    """
    os.makedirs(output_directory, exist_ok=True)
    metadata_file_path = os.path.join(output_directory, "metadata.json")

    # Check if the file is ole2 file.
    if not olefile.isOleFile(ole_file_path):
        message = f"The file {ole_file_path} is not an OLE2 file."
        print(message)
        with open(metadata_file_path, "w") as metadata_file:
            metadata_file.write(message)
        return

    # Open the OLE2 file.
    ole = olefile.OleFileIO(ole_file_path)

    # Get the metadata of the OLE2 file.
    metadata = ole.get_metadata()

    meta_properties: dict = {
        'SummaryInformation': {},
        'DocumentSummaryInformation': {}
    }
    # Properties from SummaryInformation stream.
    for prop in metadata.SUMMARY_ATTRIBS:
        value = getattr(metadata, prop)
        value = convert_object_to_string(value)
        meta_properties['SummaryInformation'][prop] = value
    # Properties from DocumentSummaryInformation stream.
    for prop in metadata.DOCSUM_ATTRIBS:
        value = getattr(metadata, prop)
        value = convert_object_to_string(value)
        meta_properties['DocumentSummaryInformation'][prop] = value

    # Save the metadata to a file.
    with open(metadata_file_path, "w") as metadata_file:
        json.dump(meta_properties, metadata_file, indent=4)

    print(f"Metadata of the OLE2 file saved to {metadata_file_path}")

    # Close the OLE2 file.
    ole.close()
