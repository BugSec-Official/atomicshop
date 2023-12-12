import docker

from ...print_api import print_api


def get_images():
    """
    Show all images in the local registry
    Usages:
        from atomicshop.wrappers.dockerw import dockerw
        images = dockerw.get_images()
        for image in images:
            print(f"ID: {image.id} Tags: {image.tags}")
    """
    client = docker.from_env()
    images = client.images.list()

    return images


def remove_image(image_id_or_tag: str, print_kwargs: dict = None):
    """
    Remove an image from the local registry by providing the image id or tag.
    :param image_id_or_tag: string, the image id or tag.
    :param print_kwargs: dict, the print arguments.
    :return:
    """

    if print_kwargs is None:
        print_kwargs = {}

    client = docker.from_env()

    client.images.remove(image_id_or_tag)
    print_api(f"Image {image_id_or_tag} removed successfully.", **print_kwargs)
