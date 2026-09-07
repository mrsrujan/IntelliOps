{{- define "ui.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ui.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{ include "ui.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "ui.selectorLabels" -}}
app.kubernetes.io/name: ui
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
