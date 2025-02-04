"""
Need to fix the
etw.etw
file, in the
EventConsumer._unpackSimpleType
function.
"""
"""
data = formatted_data.value
# Convert the formatted data if necessary
if isinstance(data, str):
    if data.endswith(' '):
        data = data[:-1]
else:
    if out_type in tdh.TDH_CONVERTER_LOOKUP and type(data) != tdh.TDH_CONVERTER_LOOKUP[out_type]:
        data = tdh.TDH_CONVERTER_LOOKUP[out_type](data)
"""