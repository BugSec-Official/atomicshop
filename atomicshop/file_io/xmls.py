import xml.etree.ElementTree as ET


def read_xml_file(
        file_path: str,
        **kwargs):
    """
    Read the xml file and return its content as dictionary.
    :param file_path: string, full path to xml file.
    :param kwargs: dict, keyword arguments for print_api function.
    :return:
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

    tree = ET.parse(file_path)
    root = tree.getroot()
    result_xml_dict: dict = xml_to_dict(root)

    return result_xml_dict, tree, root
