{{- define "payment-service.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "payment-service.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{ include "payment-service.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "payment-service.selectorLabels" -}}
app.kubernetes.io/name: payment-service
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
