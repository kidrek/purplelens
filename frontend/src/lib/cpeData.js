/**
 * Référentiel CPE local (Common Platform Enumeration - NIST NVD)
 * Format : { cpe, vendor, product }
 *
 * Ce fichier peut être régénéré depuis l'API NVD :
 *   GET https://services.nvd.nist.gov/rest/json/cpes/2.0
 * via la page Paramètres > Mise à jour du référentiel CPE.
 */

export const CPE_DATA = [
  // ── Serveurs web & proxys ─────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*",       vendor: "Apache",      product: "HTTP Server" },
  { cpe: "cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*",               vendor: "Nginx",       product: "Nginx" },
  { cpe: "cpe:2.3:a:microsoft:internet_information_server:*",    vendor: "Microsoft",   product: "IIS" },
  { cpe: "cpe:2.3:a:lighttpd:lighttpd:*:*:*:*:*:*:*:*",         vendor: "Lighttpd",    product: "Lighttpd" },
  { cpe: "cpe:2.3:a:haproxy:haproxy:*:*:*:*:*:*:*:*",           vendor: "HAProxy",     product: "HAProxy" },
  { cpe: "cpe:2.3:a:traefik:traefik:*:*:*:*:*:*:*:*",           vendor: "Traefik",     product: "Traefik" },
  { cpe: "cpe:2.3:a:squid-cache:squid:*:*:*:*:*:*:*:*",         vendor: "Squid",       product: "Squid Proxy" },
  { cpe: "cpe:2.3:a:f5:nginx_plus:*:*:*:*:*:*:*:*",             vendor: "F5",          product: "NGINX Plus" },

  // ── Bases de données relationnelles ──────────────────────────────────────
  { cpe: "cpe:2.3:a:postgresql:postgresql:*:*:*:*:*:*:*:*",     vendor: "PostgreSQL",  product: "PostgreSQL" },
  { cpe: "cpe:2.3:a:mysql:mysql:*:*:*:*:*:*:*:*",               vendor: "MySQL",       product: "MySQL" },
  { cpe: "cpe:2.3:a:oracle:mysql:*:*:*:*:*:*:*:*",              vendor: "Oracle",      product: "MySQL (Oracle)" },
  { cpe: "cpe:2.3:a:mariadb:mariadb:*:*:*:*:*:*:*:*",           vendor: "MariaDB",     product: "MariaDB" },
  { cpe: "cpe:2.3:a:microsoft:sql_server:*:*:*:*:*:*:*:*",      vendor: "Microsoft",   product: "SQL Server" },
  { cpe: "cpe:2.3:a:oracle:database_server:*:*:*:*:*:*:*:*",    vendor: "Oracle",      product: "Oracle Database" },
  { cpe: "cpe:2.3:a:sqlite:sqlite:*:*:*:*:*:*:*:*",             vendor: "SQLite",      product: "SQLite" },
  { cpe: "cpe:2.3:a:ibm:db2:*:*:*:*:*:*:*:*",                  vendor: "IBM",         product: "DB2" },

  // ── Bases de données NoSQL / cache ───────────────────────────────────────
  { cpe: "cpe:2.3:a:redis:redis:*:*:*:*:*:*:*:*",               vendor: "Redis",       product: "Redis" },
  { cpe: "cpe:2.3:a:mongodb:mongodb:*:*:*:*:*:*:*:*",           vendor: "MongoDB",     product: "MongoDB" },
  { cpe: "cpe:2.3:a:elastic:elasticsearch:*:*:*:*:*:*:*:*",     vendor: "Elastic",     product: "Elasticsearch" },
  { cpe: "cpe:2.3:a:apache:cassandra:*:*:*:*:*:*:*:*",          vendor: "Apache",      product: "Cassandra" },
  { cpe: "cpe:2.3:a:apache:couchdb:*:*:*:*:*:*:*:*",            vendor: "Apache",      product: "CouchDB" },
  { cpe: "cpe:2.3:a:memcached:memcached:*:*:*:*:*:*:*:*",       vendor: "Memcached",   product: "Memcached" },
  { cpe: "cpe:2.3:a:neo4j:neo4j:*:*:*:*:*:*:*:*",               vendor: "Neo4j",       product: "Neo4j" },
  { cpe: "cpe:2.3:a:influxdata:influxdb:*:*:*:*:*:*:*:*",       vendor: "InfluxData",  product: "InfluxDB" },
  { cpe: "cpe:2.3:a:couchbase:couchbase_server:*:*:*:*:*:*:*:*",vendor: "Couchbase",   product: "Couchbase Server" },

  // ── Langages / runtimes ───────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:python:python:*:*:*:*:*:*:*:*",             vendor: "Python",      product: "Python" },
  { cpe: "cpe:2.3:a:nodejs:node.js:*:*:*:*:*:*:*:*",            vendor: "Node.js",     product: "Node.js" },
  { cpe: "cpe:2.3:a:php:php:*:*:*:*:*:*:*:*",                   vendor: "PHP",         product: "PHP" },
  { cpe: "cpe:2.3:a:ruby-lang:ruby:*:*:*:*:*:*:*:*",            vendor: "Ruby",        product: "Ruby" },
  { cpe: "cpe:2.3:a:oracle:jdk:*:*:*:*:*:*:*:*",                vendor: "Oracle",      product: "Java JDK" },
  { cpe: "cpe:2.3:a:oracle:jre:*:*:*:*:*:*:*:*",                vendor: "Oracle",      product: "Java JRE" },
  { cpe: "cpe:2.3:a:openjdk:openjdk:*:*:*:*:*:*:*:*",           vendor: "OpenJDK",     product: "OpenJDK" },
  { cpe: "cpe:2.3:a:golang:go:*:*:*:*:*:*:*:*",                 vendor: "Google",      product: "Go (Golang)" },
  { cpe: "cpe:2.3:a:rust-lang:rust:*:*:*:*:*:*:*:*",            vendor: "Rust",        product: "Rust" },
  { cpe: "cpe:2.3:a:microsoft:dotnet:*:*:*:*:*:*:*:*",          vendor: "Microsoft",   product: ".NET" },
  { cpe: "cpe:2.3:a:perl:perl:*:*:*:*:*:*:*:*",                 vendor: "Perl",        product: "Perl" },

  // ── Frameworks applicatifs ────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:djangoproject:django:*:*:*:*:*:*:*:*",      vendor: "Django",      product: "Django" },
  { cpe: "cpe:2.3:a:palletsprojects:flask:*:*:*:*:*:*:*:*",     vendor: "Pallets",     product: "Flask" },
  { cpe: "cpe:2.3:a:fastapi:fastapi:*:*:*:*:*:*:*:*",           vendor: "FastAPI",     product: "FastAPI" },
  { cpe: "cpe:2.3:a:rubyonrails:ruby_on_rails:*:*:*:*:*:*:*:*", vendor: "Rails",       product: "Ruby on Rails" },
  { cpe: "cpe:2.3:a:laravel:laravel:*:*:*:*:*:*:*:*",           vendor: "Laravel",     product: "Laravel" },
  { cpe: "cpe:2.3:a:symfony:symfony:*:*:*:*:*:*:*:*",           vendor: "Symfony",     product: "Symfony" },
  { cpe: "cpe:2.3:a:spring:spring_framework:*:*:*:*:*:*:*:*",   vendor: "Spring",      product: "Spring Framework" },
  { cpe: "cpe:2.3:a:spring:spring_boot:*:*:*:*:*:*:*:*",        vendor: "Spring",      product: "Spring Boot" },
  { cpe: "cpe:2.3:a:expressjs:express:*:*:*:*:*:*:*:*",         vendor: "Express.js",  product: "Express" },
  { cpe: "cpe:2.3:a:nestjs:nest:*:*:*:*:*:*:*:*",               vendor: "NestJS",      product: "NestJS" },
  { cpe: "cpe:2.3:a:microsoft:asp.net:*:*:*:*:*:*:*:*",         vendor: "Microsoft",   product: "ASP.NET" },
  { cpe: "cpe:2.3:a:quarkus:quarkus:*:*:*:*:*:*:*:*",           vendor: "Red Hat",     product: "Quarkus" },
  { cpe: "cpe:2.3:a:micronaut:micronaut:*:*:*:*:*:*:*:*",       vendor: "Micronaut",   product: "Micronaut" },

  // ── Frameworks frontend ───────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:facebook:react:*:*:*:*:*:*:*:*",            vendor: "Meta",        product: "React" },
  { cpe: "cpe:2.3:a:vuejs:vue.js:*:*:*:*:*:*:*:*",              vendor: "Vue.js",      product: "Vue.js" },
  { cpe: "cpe:2.3:a:google:angular:*:*:*:*:*:*:*:*",            vendor: "Google",      product: "Angular" },
  { cpe: "cpe:2.3:a:svelte:svelte:*:*:*:*:*:*:*:*",             vendor: "Svelte",      product: "Svelte" },
  { cpe: "cpe:2.3:a:jquery:jquery:*:*:*:*:*:*:*:*",             vendor: "jQuery",      product: "jQuery" },
  { cpe: "cpe:2.3:a:nextjs:next.js:*:*:*:*:*:*:*:*",            vendor: "Vercel",      product: "Next.js" },
  { cpe: "cpe:2.3:a:nuxtjs:nuxt.js:*:*:*:*:*:*:*:*",            vendor: "Nuxt",        product: "Nuxt.js" },

  // ── CMS & portails ────────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:wordpress:wordpress:*:*:*:*:*:*:*:*",       vendor: "WordPress",   product: "WordPress" },
  { cpe: "cpe:2.3:a:drupal:drupal:*:*:*:*:*:*:*:*",             vendor: "Drupal",      product: "Drupal" },
  { cpe: "cpe:2.3:a:joomla:joomla\!:*:*:*:*:*:*:*:*",           vendor: "Joomla",      product: "Joomla!" },
  { cpe: "cpe:2.3:a:typo3:typo3:*:*:*:*:*:*:*:*",               vendor: "TYPO3",       product: "TYPO3" },
  { cpe: "cpe:2.3:a:magento:magento:*:*:*:*:*:*:*:*",           vendor: "Adobe",       product: "Magento" },
  { cpe: "cpe:2.3:a:confluence:confluence:*:*:*:*:*:*:*:*",     vendor: "Atlassian",   product: "Confluence" },
  { cpe: "cpe:2.3:a:atlassian:jira:*:*:*:*:*:*:*:*",            vendor: "Atlassian",   product: "Jira" },

  // ── Messagerie & files de messages ───────────────────────────────────────
  { cpe: "cpe:2.3:a:apache:kafka:*:*:*:*:*:*:*:*",              vendor: "Apache",      product: "Kafka" },
  { cpe: "cpe:2.3:a:rabbitmq:rabbitmq:*:*:*:*:*:*:*:*",         vendor: "RabbitMQ",    product: "RabbitMQ" },
  { cpe: "cpe:2.3:a:apache:activemq:*:*:*:*:*:*:*:*",           vendor: "Apache",      product: "ActiveMQ" },
  { cpe: "cpe:2.3:a:nats:nats.io:*:*:*:*:*:*:*:*",              vendor: "NATS",        product: "NATS" },

  // ── Conteneurs & orchestration ────────────────────────────────────────────
  { cpe: "cpe:2.3:a:docker:docker:*:*:*:*:*:*:*:*",             vendor: "Docker",      product: "Docker Engine" },
  { cpe: "cpe:2.3:a:kubernetes:kubernetes:*:*:*:*:*:*:*:*",     vendor: "Kubernetes",  product: "Kubernetes" },
  { cpe: "cpe:2.3:a:redhat:openshift:*:*:*:*:*:*:*:*",          vendor: "Red Hat",     product: "OpenShift" },
  { cpe: "cpe:2.3:a:rancher_labs:rancher:*:*:*:*:*:*:*:*",      vendor: "Rancher",     product: "Rancher" },
  { cpe: "cpe:2.3:a:containerd:containerd:*:*:*:*:*:*:*:*",     vendor: "containerd",  product: "containerd" },
  { cpe: "cpe:2.3:a:podman:podman:*:*:*:*:*:*:*:*",             vendor: "Red Hat",     product: "Podman" },

  // ── CI/CD & DevOps ────────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:jenkins:jenkins:*:*:*:*:*:*:*:*",           vendor: "Jenkins",     product: "Jenkins" },
  { cpe: "cpe:2.3:a:gitlab:gitlab:*:*:*:*:*:*:*:*",             vendor: "GitLab",      product: "GitLab" },
  { cpe: "cpe:2.3:a:github:github_enterprise_server:*",          vendor: "GitHub",      product: "GitHub Enterprise" },
  { cpe: "cpe:2.3:a:ansible:ansible:*:*:*:*:*:*:*:*",           vendor: "Red Hat",     product: "Ansible" },
  { cpe: "cpe:2.3:a:hashicorp:terraform:*:*:*:*:*:*:*:*",       vendor: "HashiCorp",   product: "Terraform" },
  { cpe: "cpe:2.3:a:hashicorp:vault:*:*:*:*:*:*:*:*",           vendor: "HashiCorp",   product: "Vault" },
  { cpe: "cpe:2.3:a:puppet:puppet:*:*:*:*:*:*:*:*",             vendor: "Puppet",      product: "Puppet" },
  { cpe: "cpe:2.3:a:chef:chef:*:*:*:*:*:*:*:*",                 vendor: "Chef",        product: "Chef" },

  // ── Systèmes d'exploitation serveur ──────────────────────────────────────
  { cpe: "cpe:2.3:o:linux:linux_kernel:*:*:*:*:*:*:*:*",        vendor: "Linux",       product: "Linux Kernel" },
  { cpe: "cpe:2.3:o:canonical:ubuntu_linux:*:*:*:*:*:*:*:*",    vendor: "Canonical",   product: "Ubuntu" },
  { cpe: "cpe:2.3:o:debian:debian_linux:*:*:*:*:*:*:*:*",       vendor: "Debian",      product: "Debian" },
  { cpe: "cpe:2.3:o:redhat:enterprise_linux:*:*:*:*:*:*:*:*",   vendor: "Red Hat",     product: "RHEL" },
  { cpe: "cpe:2.3:o:centos:centos:*:*:*:*:*:*:*:*",             vendor: "CentOS",      product: "CentOS" },
  { cpe: "cpe:2.3:o:amazon:linux:*:*:*:*:*:*:*:*",              vendor: "Amazon",      product: "Amazon Linux" },
  { cpe: "cpe:2.3:o:microsoft:windows_server_2019:*",            vendor: "Microsoft",   product: "Windows Server 2019" },
  { cpe: "cpe:2.3:o:microsoft:windows_server_2022:*",            vendor: "Microsoft",   product: "Windows Server 2022" },
  { cpe: "cpe:2.3:o:microsoft:windows_10:*:*:*:*:*:*:*:*",      vendor: "Microsoft",   product: "Windows 10" },
  { cpe: "cpe:2.3:o:microsoft:windows_11:*:*:*:*:*:*:*:*",      vendor: "Microsoft",   product: "Windows 11" },
  { cpe: "cpe:2.3:o:freebsd:freebsd:*:*:*:*:*:*:*:*",           vendor: "FreeBSD",     product: "FreeBSD" },
  { cpe: "cpe:2.3:o:alpine:alpine_linux:*:*:*:*:*:*:*:*",       vendor: "Alpine",      product: "Alpine Linux" },

  // ── Virtualisation ────────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:vmware:esxi:*:*:*:*:*:*:*:*",               vendor: "VMware",      product: "VMware ESXi" },
  { cpe: "cpe:2.3:a:vmware:vcenter_server:*:*:*:*:*:*:*:*",     vendor: "VMware",      product: "VMware vCenter" },
  { cpe: "cpe:2.3:a:vmware:workstation:*:*:*:*:*:*:*:*",        vendor: "VMware",      product: "VMware Workstation" },
  { cpe: "cpe:2.3:a:proxmox:virtual_environment:*",              vendor: "Proxmox",     product: "Proxmox VE" },
  { cpe: "cpe:2.3:a:xen:xen:*:*:*:*:*:*:*:*",                   vendor: "Xen",         product: "Xen Hypervisor" },
  { cpe: "cpe:2.3:a:microsoft:hyper-v:*:*:*:*:*:*:*:*",         vendor: "Microsoft",   product: "Hyper-V" },

  // ── Sécurité & PKI ───────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*",           vendor: "OpenSSL",     product: "OpenSSL" },
  { cpe: "cpe:2.3:a:mozilla:nss:*:*:*:*:*:*:*:*",               vendor: "Mozilla",     product: "NSS" },
  { cpe: "cpe:2.3:a:f5:big-ip:*:*:*:*:*:*:*:*",                 vendor: "F5",          product: "BIG-IP" },
  { cpe: "cpe:2.3:a:paloaltonetworks:pan-os:*:*:*:*:*:*:*:*",   vendor: "Palo Alto",   product: "PAN-OS" },
  { cpe: "cpe:2.3:a:fortinet:fortios:*:*:*:*:*:*:*:*",          vendor: "Fortinet",    product: "FortiOS" },
  { cpe: "cpe:2.3:a:cisco:ios:*:*:*:*:*:*:*:*",                 vendor: "Cisco",       product: "Cisco IOS" },
  { cpe: "cpe:2.3:a:cisco:asa:*:*:*:*:*:*:*:*",                 vendor: "Cisco",       product: "Cisco ASA" },
  { cpe: "cpe:2.3:a:checkpoint:firewall-1:*:*:*:*:*:*:*:*",     vendor: "Check Point", product: "Firewall-1" },
  { cpe: "cpe:2.3:a:keepass:keepass:*:*:*:*:*:*:*:*",           vendor: "KeePass",     product: "KeePass" },

  // ── Navigateurs ───────────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:mozilla:firefox:*:*:*:*:*:*:*:*",           vendor: "Mozilla",     product: "Firefox" },
  { cpe: "cpe:2.3:a:google:chrome:*:*:*:*:*:*:*:*",             vendor: "Google",      product: "Chrome" },
  { cpe: "cpe:2.3:a:microsoft:edge:*:*:*:*:*:*:*:*",            vendor: "Microsoft",   product: "Edge" },
  { cpe: "cpe:2.3:a:apple:safari:*:*:*:*:*:*:*:*",              vendor: "Apple",       product: "Safari" },
  { cpe: "cpe:2.3:a:opera:opera_browser:*:*:*:*:*:*:*:*",       vendor: "Opera",       product: "Opera" },

  // ── Monitoring & observabilité ────────────────────────────────────────────
  { cpe: "cpe:2.3:a:elastic:kibana:*:*:*:*:*:*:*:*",            vendor: "Elastic",     product: "Kibana" },
  { cpe: "cpe:2.3:a:elastic:logstash:*:*:*:*:*:*:*:*",          vendor: "Elastic",     product: "Logstash" },
  { cpe: "cpe:2.3:a:grafana:grafana:*:*:*:*:*:*:*:*",           vendor: "Grafana",     product: "Grafana" },
  { cpe: "cpe:2.3:a:prometheus:prometheus:*:*:*:*:*:*:*:*",     vendor: "Prometheus",  product: "Prometheus" },
  { cpe: "cpe:2.3:a:datadog:datadog-agent:*:*:*:*:*:*:*:*",     vendor: "Datadog",     product: "Datadog Agent" },
  { cpe: "cpe:2.3:a:zabbix:zabbix:*:*:*:*:*:*:*:*",             vendor: "Zabbix",      product: "Zabbix" },
  { cpe: "cpe:2.3:a:nagios:nagios:*:*:*:*:*:*:*:*",             vendor: "Nagios",      product: "Nagios" },
  { cpe: "cpe:2.3:a:splunk:splunk:*:*:*:*:*:*:*:*",             vendor: "Splunk",      product: "Splunk" },
  { cpe: "cpe:2.3:a:graylog:graylog:*:*:*:*:*:*:*:*",           vendor: "Graylog",     product: "Graylog" },

  // ── Bibliothèques critiques (CVE fréquentes) ──────────────────────────────
  { cpe: "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",              vendor: "Apache",      product: "Log4j" },
  { cpe: "cpe:2.3:a:apache:struts:*:*:*:*:*:*:*:*",             vendor: "Apache",      product: "Struts" },
  { cpe: "cpe:2.3:a:spring:spring_security:*:*:*:*:*:*:*:*",    vendor: "Spring",      product: "Spring Security" },
  { cpe: "cpe:2.3:a:shiro:shiro:*:*:*:*:*:*:*:*",               vendor: "Apache",      product: "Shiro" },
  { cpe: "cpe:2.3:a:imagemagick:imagemagick:*:*:*:*:*:*:*:*",   vendor: "ImageMagick", product: "ImageMagick" },
  { cpe: "cpe:2.3:a:libpng:libpng:*:*:*:*:*:*:*:*",             vendor: "libpng",      product: "libpng" },
  { cpe: "cpe:2.3:a:curl:curl:*:*:*:*:*:*:*:*",                 vendor: "curl",        product: "curl" },
  { cpe: "cpe:2.3:a:libssh:libssh:*:*:*:*:*:*:*:*",             vendor: "libssh",      product: "libssh" },
  { cpe: "cpe:2.3:a:zlib:zlib:*:*:*:*:*:*:*:*",                 vendor: "zlib",        product: "zlib" },

  // ── Cloud & stockage objet ────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:amazon:aws_s3:*:*:*:*:*:*:*:*",             vendor: "Amazon",      product: "AWS S3" },
  { cpe: "cpe:2.3:a:amazon:aws_lambda:*:*:*:*:*:*:*:*",         vendor: "Amazon",      product: "AWS Lambda" },
  { cpe: "cpe:2.3:a:amazon:cloudfront:*:*:*:*:*:*:*:*",         vendor: "Amazon",      product: "AWS CloudFront" },
  { cpe: "cpe:2.3:a:microsoft:azure:*:*:*:*:*:*:*:*",           vendor: "Microsoft",   product: "Microsoft Azure" },
  { cpe: "cpe:2.3:a:google:cloud_platform:*:*:*:*:*:*:*:*",     vendor: "Google",      product: "Google Cloud Platform" },
  { cpe: "cpe:2.3:a:minio:minio:*:*:*:*:*:*:*:*",               vendor: "MinIO",       product: "MinIO" },

  // ── Applications métier ───────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:sap:netweaver:*:*:*:*:*:*:*:*",             vendor: "SAP",         product: "SAP NetWeaver" },
  { cpe: "cpe:2.3:a:sap:businessobjects:*:*:*:*:*:*:*:*",       vendor: "SAP",         product: "SAP BusinessObjects" },
  { cpe: "cpe:2.3:a:oracle:e-business_suite:*:*:*:*:*:*:*:*",   vendor: "Oracle",      product: "Oracle E-Business Suite" },
  { cpe: "cpe:2.3:a:microsoft:exchange_server:*:*:*:*:*:*:*:*", vendor: "Microsoft",   product: "Exchange Server" },
  { cpe: "cpe:2.3:a:microsoft:sharepoint_server:*",              vendor: "Microsoft",   product: "SharePoint Server" },
  { cpe: "cpe:2.3:a:microsoft:office:*:*:*:*:*:*:*:*",          vendor: "Microsoft",   product: "Microsoft Office" },
  { cpe: "cpe:2.3:a:adobe:acrobat_reader:*:*:*:*:*:*:*:*",      vendor: "Adobe",       product: "Acrobat Reader" },
  { cpe: "cpe:2.3:a:adobe:coldfusion:*:*:*:*:*:*:*:*",          vendor: "Adobe",       product: "ColdFusion" },

  // ── Annuaire & IAM ───────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:microsoft:active_directory:*:*:*:*:*:*:*:*",vendor: "Microsoft",   product: "Active Directory" },
  { cpe: "cpe:2.3:a:openldap:openldap:*:*:*:*:*:*:*:*",         vendor: "OpenLDAP",    product: "OpenLDAP" },
  { cpe: "cpe:2.3:a:keycloak:keycloak:*:*:*:*:*:*:*:*",         vendor: "Red Hat",     product: "Keycloak" },
  { cpe: "cpe:2.3:a:okta:okta:*:*:*:*:*:*:*:*",                 vendor: "Okta",        product: "Okta" },
  { cpe: "cpe:2.3:a:freeipa:freeipa:*:*:*:*:*:*:*:*",           vendor: "Red Hat",     product: "FreeIPA" },

  // ── Serveurs d'applications Java ─────────────────────────────────────────
  { cpe: "cpe:2.3:a:apache:tomcat:*:*:*:*:*:*:*:*",             vendor: "Apache",      product: "Tomcat" },
  { cpe: "cpe:2.3:a:redhat:jboss_application_server:*",          vendor: "Red Hat",     product: "JBoss / WildFly" },
  { cpe: "cpe:2.3:a:oracle:weblogic_server:*:*:*:*:*:*:*:*",    vendor: "Oracle",      product: "WebLogic Server" },
  { cpe: "cpe:2.3:a:ibm:websphere_application_server:*",         vendor: "IBM",         product: "WebSphere" },
  { cpe: "cpe:2.3:a:eclipse:jetty:*:*:*:*:*:*:*:*",             vendor: "Eclipse",     product: "Jetty" },

  // ── Réseau ────────────────────────────────────────────────────────────────
  { cpe: "cpe:2.3:a:openvpn:openvpn:*:*:*:*:*:*:*:*",           vendor: "OpenVPN",     product: "OpenVPN" },
  { cpe: "cpe:2.3:a:wireguard:wireguard:*:*:*:*:*:*:*:*",       vendor: "WireGuard",   product: "WireGuard" },
  { cpe: "cpe:2.3:a:openssh:openssh:*:*:*:*:*:*:*:*",           vendor: "OpenSSH",     product: "OpenSSH" },
  { cpe: "cpe:2.3:a:isc:bind:*:*:*:*:*:*:*:*",                  vendor: "ISC",         product: "BIND (DNS)" },
  { cpe: "cpe:2.3:a:isc:dhcp:*:*:*:*:*:*:*:*",                  vendor: "ISC",         product: "ISC DHCP" },
  { cpe: "cpe:2.3:a:vsftpd:vsftpd:*:*:*:*:*:*:*:*",             vendor: "vsftpd",      product: "vsftpd" },
  { cpe: "cpe:2.3:a:proftpd:proftpd:*:*:*:*:*:*:*:*",           vendor: "ProFTPD",     product: "ProFTPD" },
  { cpe: "cpe:2.3:a:postfix:postfix:*:*:*:*:*:*:*:*",           vendor: "Postfix",     product: "Postfix" },
  { cpe: "cpe:2.3:a:dovecot:dovecot:*:*:*:*:*:*:*:*",           vendor: "Dovecot",     product: "Dovecot" },
  { cpe: "cpe:2.3:a:samba:samba:*:*:*:*:*:*:*:*",               vendor: "Samba",       product: "Samba" },
];

/**
 * Recherche dans le référentiel CPE local.
 * @param {string} query - texte saisi par l'utilisateur
 * @param {number} limit - nombre max de résultats
 * @returns {Array} entrées CPE correspondantes
 */
export function searchCPE(query, limit = 10) {
  if (!query || query.trim().length < 2) return [];
  const q = query.toLowerCase().trim();
  return CPE_DATA.filter(
    (c) =>
      c.product.toLowerCase().includes(q) ||
      c.vendor.toLowerCase().includes(q)
  ).slice(0, limit);
}

/**
 * Convertit une chaîne JSON stockée en base (technologies_cpe)
 * en tableau d'objets { cpe, vendor, product }.
 */
export function parseTechnologiesCpe(raw) {
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

/**
 * Sérialise le tableau d'objets CPE en JSON pour stockage backend.
 */
export function serializeTechnologiesCpe(items) {
  return JSON.stringify(items.map(({ cpe, vendor, product }) => ({ cpe, vendor, product })));
}

/**
 * Génère la chaîne lisible (ex: "Nginx, PostgreSQL, Apache Tomcat")
 * à partir du tableau d'objets CPE.
 */
export function cpeToReadable(items) {
  return items.map((i) => `${i.vendor} ${i.product}`).join(", ");
}
