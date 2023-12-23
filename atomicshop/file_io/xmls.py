import xml.etree.ElementTree as ET


def read_xml(
        file_path: str = None,
        xml_bytes: bytes = None,
):
    """
    Read XML from a file or bytes and return its content as a dictionary.
    :param file_path: Optional string, full path to xml file.
    :param xml_bytes: Optional bytes, XML data as bytes.
    :return: Tuple containing the XML dictionary, the ElementTree, and the root element.
    """

    def xml_to_dict(element):
        # Create a dictionary to hold the element data
        element_dict = {}

        # Include element attributes in the dictionary
        element_dict.update(element.attrib)

        # Handle child elements
        for child in element:
            # Recursive call for each child element
            child_dict = xml_to_dict(child)

            # Handle multiple child elements with the same tag
            if child.tag in element_dict:
                # If this tag is already in the dictionary, ensure its value is a list
                if not isinstance(element_dict[child.tag], list):
                    element_dict[child.tag] = [element_dict[child.tag]]
                # Append the child dictionary to the list
                element_dict[child.tag].append(child_dict)
            else:
                # Otherwise, just add the child dictionary to the element dictionary
                element_dict[child.tag] = child_dict

        # Include element text, if any
        if element.text and element.text.strip():
            element_dict['#text'] = element.text.strip()

        return element_dict

    # Determine source of XML data
    if xml_bytes is not None:
        # Parse XML from bytes object
        root = ET.fromstring(xml_bytes)
        tree = ET.ElementTree(root)
    elif file_path is not None:
        # Parse XML from file
        tree = ET.parse(file_path)
        root = tree.getroot()
    else:
        raise ValueError("Either file_path or xml_bytes must be provided")

    result_xml_dict: dict = xml_to_dict(root)

    return result_xml_dict, tree, root
