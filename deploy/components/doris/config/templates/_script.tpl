{{- define "doris.initScript" -}}
FE={{ .Values.fe }}
DB=ctx_{{ .Values.tenantId }}
# 首次运行时 root 无密码：设置为 Secret 中的密码（之后的运行直接用该密码登录）。
# 用 SHOW FRONTENDS 判断（只读元数据，不需要 BE 就绪）
if mysql -h "$FE" -P 9030 -uroot -e "SHOW FRONTENDS" >/dev/null 2>&1; then
  mysql -h "$FE" -P 9030 -uroot -e "SET PASSWORD FOR 'root' = PASSWORD('$ROOT_PASSWORD')"
fi
mysql -h "$FE" -P 9030 -uroot -p"$ROOT_PASSWORD" <<SQL
CREATE DATABASE IF NOT EXISTS $DB;
CREATE USER IF NOT EXISTS 'ctx_reader'@'%' IDENTIFIED BY '$READER_PASSWORD';
SET PASSWORD FOR 'ctx_reader'@'%' = PASSWORD('$READER_PASSWORD');
GRANT SELECT_PRIV ON $DB.* TO 'ctx_reader'@'%';
CREATE WORKLOAD GROUP IF NOT EXISTS interactive PROPERTIES ("max_cpu_percent" = "100", "max_memory_percent" = "50");
CREATE WORKLOAD GROUP IF NOT EXISTS pipeline PROPERTIES ("max_cpu_percent" = "50", "max_memory_percent" = "40");
GRANT USAGE_PRIV ON WORKLOAD GROUP 'interactive' TO 'ctx_reader'@'%';
SET PROPERTY FOR 'ctx_reader' 'default_workload_group' = 'interactive';
SQL
echo "doris init done: $DB"
{{- end }}
