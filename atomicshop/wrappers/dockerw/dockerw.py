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
    print_api(f"Removed Image {image_id_or_tag} successfully.", color='green', **print_kwargs)


class ChangeImageByCommands(Exception):
    pass


class ChangeImageByCallback(Exception):
    pass


def change_image_content(
        image_id_or_name: str,
        list_of_commands: list[str] = None,
        print_kwargs: dict = None,
        change_callback=None, *args, **kwargs):
    """
    Change an image id or tag.
    :param image_id_or_name: string, the image id or image tag name.
    :param list_of_commands: list of strings, the commands to run in the docker container.
    :param print_kwargs: dict, the print arguments.
    :param change_callback: function callable, the function to change the image. The first argument of the function
        must be the docker container object. The rest of the arguments are optional *args and **kwargs.
        The function must return a tuple of (exit_code, output).
    :return:
    ----------------------
    Example usage by providing a list of commands:
        from atomicshop.wrappers.dockerw import dockerw
        dockerw.change_image_content(
            image_id_or_name="your_docker_image_id_or_name",
            list_of_commands=[
                "apt-get update",
                "apt-get install -y python3"
            ]
        )
    ----------------------
    Example usage by providing a command to update execution permissions of a file:
        from atomicshop.wrappers.dockerw import dockerw
        dockerw.change_image_content(
            image_id_or_name="your_docker_image_id_or_name",
            list_of_commands=[
                "chmod +x /your_script.py"
            ]
        )
    ----------------------
    Example usage by providing a callback function:
        from atomicshop.wrappers.dockerw import dockerw
        dockerw.change_image_content(
            image_id_or_name="your_docker_image_id_or_name",
            change_callback=your_callback_function,
            your_callback_function_args=(your_callback_function_arg1, your_callback_function_arg2),
            your_callback_function_kwargs={'your_callback_function_kwarg1': your_callback_function_kwarg1}
        )

        def your_callback_function(container, your_callback_function_arg1, your_callback_function_arg2,
                                   your_callback_function_kwarg1=None):
            # Do something with the container.
            # Return a tuple of (exit_code, output).
            return 0, b"Done"
    ----------------------
    Example of providing callback function that change permissions of a file:
        from atomicshop.wrappers.dockerw import dockerw
        dockerw.change_image_content(
            image_id_or_name="your_docker_image_id_or_name",
            change_callback=change_permissions,
            script_path="/your_python_script.py"
        )

        def change_permissions(container, script_path):
            return container.exec_run(f"chmod +x {script_path}")

    """

    if not list_of_commands and not change_callback:
        raise ValueError("Either list_of_commands or change_callback must be provided.")

    if print_kwargs is None:
        print_kwargs = {}

    client = docker.from_env()

    # Create and start a container from the existing image
    container = client.containers.run(image_id_or_name, "/bin/bash", entrypoint="", detach=True, tty=True)

    try:
        if list_of_commands:
            # Execute the list of commands.
            for command_index, command in enumerate(list_of_commands):
                exit_code, output = container.exec_run(command)
                if exit_code != 0:
                    raise ChangeImageByCommands(
                        f"Error in executing command [{command_index+1}]: {output.decode('utf-8')}")

        if change_callback:
            # Execute the callback function with additional arguments.
            exit_code, output = change_callback(container, *args, **kwargs)
            if exit_code != 0:
                raise ChangeImageByCallback(f"Error in Updating image with callback function: {output.decode('utf-8')}")

        # Commit the container
        new_image = container.commit()

        # Remove the original image
        client.images.remove(image_id_or_name, force=True)

        # Tag the new image with the original image's name
        client.images.get(new_image.id).tag(image_id_or_name)

        print_api(f"Updated image [{image_id_or_name}].", color='green', **print_kwargs)

    finally:
        # Clean up: Stop and remove the temporary container
        container.stop()
        container.remove()


def add_execution_permissions_for_file(image_id_or_name: str, file_path: str, print_kwargs: dict = None):
    """
    Add execution permissions for a file inside docker image.

    :param image_id_or_name: string, the image id or image tag name.
    :param file_path: string, the path to the file.
    :param print_kwargs: dict, the print arguments.
    :return:
    """

    if print_kwargs is None:
        print_kwargs = {}

    change_image_content(
        image_id_or_name=image_id_or_name,
        list_of_commands=[f"chmod +x {file_path}"],
        print_kwargs=print_kwargs
    )
