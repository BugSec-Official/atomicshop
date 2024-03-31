DEFAULT_ELASTIC_PORT: str = '9200'
DEFAULT_ELASTIC_HOST: str = 'localhost'
DEFAULT_ELASTIC_URL: str = f"http://{DEFAULT_ELASTIC_HOST}:{DEFAULT_ELASTIC_PORT}"

DEFAULT_KIBANA_PORT: str = '5601'
DEFAULT_KIBANA_HOST: str = 'localhost'
DEFAULT_KIBANA_URL: str = f"http://{DEFAULT_KIBANA_HOST}:{DEFAULT_KIBANA_PORT}"

ELASTIC_CONFIG_FILE: str = "/etc/elasticsearch/elasticsearch.yml"
ELASTIC_JVM_OPTIONS_FILE: str = "/etc/elasticsearch/jvm.options"
XPACK_SECURITY_SETTING_NAME: str = "xpack.security.enabled"

UBUNTU_DEPENDENCY_PACKAGES: list[str] = ['apt-transport-https', 'openjdk-11-jdk', 'wget']
UBUNTU_ELASTIC_PACKAGE_NAME: str = 'elasticsearch'
UBUNTU_ELASTIC_SERVICE_NAME: str = 'elasticsearch'
UBUNTU_KIBANA_PACKAGE_NAME: str = 'kibana'
UBUNTU_KIBANA_SERVICE_NAME: str = 'kibana'
