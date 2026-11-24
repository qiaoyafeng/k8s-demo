{{/*
_helpers.tpl：Chart 的命名与标签约定
所有资源通过 include 引用这里的 define，保证：
1. 命名一致（release 名 + chart 名组合，支持 nameOverride/fullnameOverride）；
2. 标签一致（selectorLabels 必须与 Deployment 的 matchLabels 严格一致，
   否则 Service 无法选中 Pod，这是 Helm 新手最常见的坑）。
*/}}

{{/* Chart 名 */}}
{{- define "k8s-demo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* 资源全名：release 名 + chart 名（如 k8s-demo-prod-k8s-demo） */}}
{{- define "k8s-demo.fullname" -}}
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

{{/* Chart 版本标签（+ 替换为 _ 以满足 K8s 标签值限制） */}}
{{- define "k8s-demo.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* 资源通用标签 */}}
{{- define "k8s-demo.labels" -}}
helm.sh/chart: {{ include "k8s-demo.chart" . }}
{{ include "k8s-demo.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* 选择器标签：Deployment matchLabels 与 Service selector 共用 */}}
{{- define "k8s-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "k8s-demo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
