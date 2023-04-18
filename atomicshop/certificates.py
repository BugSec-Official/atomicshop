"""
Site for checking OIDs:
https://oidref.com/1.3.6.1.5.5.7.3.1
"""

# Valid for 3 years from now
# Max validity is 39 months:
# https://casecurity.org/2015/02/19/ssl-certificate-validity-periods-limited-to-39-months-starting-in-april/
SECONDS_NOT_AFTER_3_YEARS = 3 * 365 * 24 * 60 * 60
