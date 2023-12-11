def put_args_to_kwargs(source_function_name, *args, **kwargs):
    # If this function is executed against class function that belongs to that class, first entry of
    # 'source_function_name.__code__.co_varnames' will be 'self'.

    # 'args' is a tuple, even if it is empty, no exception will be thrown.
    kwargs.update(zip(source_function_name.__code__.co_varnames, args))
    # args can be nullified if you already have everything in 'kwargs'.
    args = ()

    return args, kwargs
