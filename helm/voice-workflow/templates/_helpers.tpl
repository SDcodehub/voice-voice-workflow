{{/*
Expand the name of the chart.
*/}}
{{- define "voice-workflow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "voice-workflow.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "voice-workflow.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "voice-workflow.labels" -}}
helm.sh/chart: {{ include "voice-workflow.chart" . }}
{{ include "voice-workflow.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "voice-workflow.selectorLabels" -}}
app.kubernetes.io/name: {{ include "voice-workflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the namespace
*/}}
{{- define "voice-workflow.namespace" -}}
{{- if .Values.namespace.create }}
{{- default .Release.Namespace .Values.namespace.name }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
NGC Secret name
*/}}
{{- define "voice-workflow.ngcSecretName" -}}
{{- if .Values.ngc.existingSecret }}
{{- .Values.ngc.existingSecret }}
{{- else }}
{{- include "voice-workflow.fullname" . }}-ngc
{{- end }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "voice-workflow.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- else if .Values.ngc.apiKey }}
imagePullSecrets:
  - name: {{ include "voice-workflow.ngcSecretName" . }}
{{- end }}
{{- end }}

{{/*
Riva server URL
*/}}
{{- define "voice-workflow.rivaServerUrl" -}}
{{- if .Values.rivaServer.enabled }}
{{- printf "%s-riva-server:50051" (include "voice-workflow.fullname" .) }}
{{- else }}
{{- .Values.rivaServer.externalUrl | default "riva-server:50051" }}
{{- end }}
{{- end }}

{{/*
NIM LLM URL
*/}}
{{- define "voice-workflow.nimLlmUrl" -}}
{{- if .Values.nimLlm.enabled }}
{{- printf "http://%s-nim-llm:8000/v1" (include "voice-workflow.fullname" .) }}
{{- else }}
{{- .Values.nimLlm.externalUrl | default "http://nim-llm:8000/v1" }}
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "voice-workflow.redisHost" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" .Release.Name }}
{{- else }}
{{- .Values.redis.externalHost | default "redis" }}
{{- end }}
{{- end }}

