{{- define "bff.labels" -}}
app.kubernetes.io/name: bff
app.kubernetes.io/part-of: contexture
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "bff.selector" -}}
app.kubernetes.io/name: bff
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "bff.env" -}}
- { name: CTX_TENANT_ID, value: {{ .Values.config.tenantId | quote }} }
- { name: CTX_PUBLIC_URL, value: {{ .Values.config.publicUrl | quote }} }
- { name: CTX_KEYCLOAK_URL, value: {{ .Values.config.keycloakUrl | quote }} }
- { name: CTX_KEYCLOAK_REALM, value: {{ .Values.config.keycloakRealm | quote }} }
- { name: CTX_AI_GATEWAY_MCP_URL, value: {{ .Values.config.aiGatewayMcpUrl | quote }} }
- { name: CTX_OM_URL, value: {{ .Values.config.omUrl | quote }} }
- { name: CTX_OM_GLOSSARY, value: {{ .Values.config.omGlossary | quote }} }
- { name: CTX_OTEL_EXPORTER_OTLP_ENDPOINT, value: {{ .Values.config.otelEndpoint | quote }} }
- { name: CTX_CLIENT_ID, value: contexture-bff }
- { name: CTX_SECRETS_DIR, value: /run/secrets/contexture }
{{- if .Values.trustedCaSecret }}
- { name: SSL_CERT_FILE, value: /etc/contexture/ca/ca.crt }
{{- end }}
{{- end }}

{{- define "bff.volumeMounts" -}}
- { name: secrets, mountPath: /run/secrets/contexture, readOnly: true }
- { name: tmp, mountPath: /tmp }
{{- if .Values.trustedCaSecret }}
- { name: trusted-ca, mountPath: /etc/contexture/ca, readOnly: true }
{{- end }}
{{- end }}

{{- define "bff.volumes" -}}
- name: secrets
  secret: { secretName: {{ .Values.existingSecret }} }
- name: tmp
  emptyDir: {}
{{- if .Values.trustedCaSecret }}
- name: trusted-ca
  secret: { secretName: {{ .Values.trustedCaSecret }} }
{{- end }}
{{- end }}

{{- define "bff.securityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities: { drop: [ALL] }
seccompProfile: { type: RuntimeDefault }
{{- end }}
