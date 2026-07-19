<script setup>
import { computed, onMounted, ref } from 'vue'
import { askQuestion, listFiles, uploadFile } from '../api'

const allowedTypes = ['txt', 'pdf', 'docx']
const selectedFile = ref(null)
const files = ref([])
const uploadLoading = ref(false)
const filesLoading = ref(false)
const chatLoading = ref(false)
const uploadError = ref('')
const filesError = ref('')
const chatError = ref('')
const uploadMessage = ref('')
const question = ref('')
const sessionId = ref(null)
const answer = ref(null)

const statusLabels = {
  UPLOADED: '已上传',
  PROCESSING: '处理中',
  SUCCESS: '已入库',
  FAILED: '失败'
}

const statusDescriptions = {
  UPLOADED: '等待入库',
  PROCESSING: '解析与向量化中',
  SUCCESS: '可参与问答',
  FAILED: '查看错误信息'
}

const hasFiles = computed(() => files.value.length > 0)
const hasAnswer = computed(() => Boolean(answer.value?.answer))
const canAsk = computed(() => question.value.trim().length > 0 && !chatLoading.value)

function getFileType(fileName = '') {
  const parts = fileName.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

function formatFileSize(size) {
  if (!size && size !== 0) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatScore(score) {
  if (typeof score !== 'number') return '-'
  return score.toFixed(3)
}

function metadataText(metadata) {
  if (!metadata || typeof metadata !== 'object') return ''
  return Object.entries(metadata)
    .map(([key, value]) => `${key}: ${value}`)
    .join(' / ')
}

function clearErrors() {
  uploadError.value = ''
  filesError.value = ''
  chatError.value = ''
}

function handleFileChange(event) {
  uploadMessage.value = ''
  uploadError.value = ''
  const file = event.target.files?.[0]
  if (!file) {
    selectedFile.value = null
    return
  }

  const fileType = getFileType(file.name)
  if (!allowedTypes.includes(fileType)) {
    selectedFile.value = null
    uploadError.value = '仅支持 txt、pdf、docx 文件'
    event.target.value = ''
    return
  }

  selectedFile.value = file
}

async function refreshFiles() {
  filesLoading.value = true
  filesError.value = ''
  try {
    files.value = await listFiles()
  } catch (error) {
    filesError.value = error.message || '文件列表加载失败'
  } finally {
    filesLoading.value = false
  }
}

async function submitUpload() {
  if (!selectedFile.value || uploadLoading.value) return

  uploadLoading.value = true
  uploadError.value = ''
  uploadMessage.value = ''

  try {
    const result = await uploadFile(selectedFile.value)
    uploadMessage.value = `${result.fileName} 已提交处理，当前状态：${statusLabels[result.status] || result.status}`
    selectedFile.value = null
    await refreshFiles()
  } catch (error) {
    uploadError.value = error.message || '文件上传失败'
  } finally {
    uploadLoading.value = false
  }
}

async function submitQuestion() {
  if (!canAsk.value) return

  chatLoading.value = true
  chatError.value = ''
  answer.value = null

  try {
    const payload = { question: question.value.trim() }
    if (sessionId.value) payload.sessionId = sessionId.value

    const result = await askQuestion(payload)
    answer.value = {
      question: result.question,
      answer: result.answer,
      references: result.references || []
    }
    sessionId.value = result.sessionId
  } catch (error) {
    chatError.value = error.message || '问答请求失败'
  } finally {
    chatLoading.value = false
  }
}

onMounted(() => {
  clearErrors()
  refreshFiles()
})
</script>

<template>
  <main class="workspace">
    <header class="topbar">
      <div>
        <p class="eyebrow">Enterprise Knowledge Base</p>
        <h1>RAG 智能问答工作台</h1>
      </div>
      <button class="ghost-button" type="button" :disabled="filesLoading" @click="refreshFiles">
        刷新文件
      </button>
    </header>

    <section class="layout">
      <aside class="panel file-panel" aria-label="文件管理">
        <div class="panel-heading">
          <div>
            <h2>文件入库</h2>
            <p>上传 txt、pdf、docx 后等待后台解析入库。</p>
          </div>
        </div>

        <label class="upload-box">
          <input type="file" accept=".txt,.pdf,.docx" @change="handleFileChange" />
          <span class="upload-title">{{ selectedFile ? selectedFile.name : '选择知识文件' }}</span>
          <span class="upload-meta">
            {{ selectedFile ? formatFileSize(selectedFile.size) : '支持 txt / pdf / docx' }}
          </span>
        </label>

        <button class="primary-button" type="button" :disabled="!selectedFile || uploadLoading" @click="submitUpload">
          {{ uploadLoading ? '上传中...' : '上传并入库' }}
        </button>

        <p v-if="uploadMessage" class="notice success">{{ uploadMessage }}</p>
        <p v-if="uploadError" class="notice error">{{ uploadError }}</p>

        <div class="section-title">
          <h2>文件列表</h2>
          <span>{{ files.length }} 个文件</span>
        </div>

        <div v-if="filesLoading" class="state">文件列表加载中...</div>
        <div v-else-if="filesError" class="state error-state">{{ filesError }}</div>
        <div v-else-if="!hasFiles" class="state">暂无文件，上传后将在这里展示状态。</div>
        <ul v-else class="file-list">
          <li v-for="file in files" :key="file.fileId" class="file-item">
            <div class="file-main">
              <strong>{{ file.fileName }}</strong>
              <span>{{ file.fileType }} · {{ formatFileSize(file.fileSize) }} · {{ file.createdAt }}</span>
            </div>
            <div class="file-status">
              <span class="status-pill" :class="`status-${file.status}`">
                {{ statusLabels[file.status] || file.status }}
              </span>
              <small>{{ statusDescriptions[file.status] || '未知状态' }}</small>
            </div>
            <div class="file-detail">
              <span>Chunks: {{ file.chunkCount ?? 0 }}</span>
              <span v-if="file.errorMsg" class="error-text">{{ file.errorMsg }}</span>
            </div>
          </li>
        </ul>
      </aside>

      <section class="panel chat-panel" aria-label="智能问答">
        <div class="panel-heading">
          <div>
            <h2>智能问答</h2>
            <p>基于已成功入库的文档检索上下文并生成回答。</p>
          </div>
          <span v-if="sessionId" class="session-chip">会话 #{{ sessionId }}</span>
        </div>

        <form class="ask-form" @submit.prevent="submitQuestion">
          <textarea
            v-model="question"
            rows="4"
            maxlength="1000"
            placeholder="输入你的问题，例如：这份制度中审批流程是什么？"
          />
          <div class="form-actions">
            <span>{{ question.length }}/1000</span>
            <button class="primary-button" type="submit" :disabled="!canAsk">
              {{ chatLoading ? '生成中...' : '提问' }}
            </button>
          </div>
        </form>

        <p v-if="chatError" class="notice error">{{ chatError }}</p>

        <div v-if="chatLoading" class="answer-state">正在检索知识库并生成回答...</div>
        <div v-else-if="!hasAnswer" class="answer-state">
          问答结果会显示在这里，引用来源会在回答下方展开。
        </div>
        <article v-else class="answer">
          <div class="question-line">
            <span>问题</span>
            <p>{{ answer.question }}</p>
          </div>
          <div class="answer-line">
            <span>回答</span>
            <p>{{ answer.answer }}</p>
          </div>

          <div class="references">
            <div class="section-title">
              <h3>引用来源</h3>
              <span>{{ answer.references.length }} 条</span>
            </div>

            <div v-if="answer.references.length === 0" class="state">本次回答没有返回引用来源。</div>
            <ol v-else class="reference-list">
              <li v-for="reference in answer.references" :key="`${reference.fileId}-${reference.chunkId || reference.chunkText}`">
                <div class="reference-head">
                  <strong>{{ reference.fileName }}</strong>
                  <span>score {{ formatScore(reference.score) }}</span>
                </div>
                <p>{{ reference.chunkText }}</p>
                <small v-if="reference.chunkId || metadataText(reference.metadata)">
                  {{ reference.chunkId || 'chunk' }}
                  <template v-if="metadataText(reference.metadata)"> · {{ metadataText(reference.metadata) }}</template>
                </small>
              </li>
            </ol>
          </div>
        </article>
      </section>
    </section>
  </main>
</template>

<style scoped>
.workspace {
  min-height: 100vh;
  padding: 32px;
  background: #f4f7fb;
  color: #172033;
  font-family:
    Inter, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

.topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  max-width: 1240px;
  margin: 0 auto 24px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #4d627d;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  font-size: 30px;
  line-height: 1.2;
}

h2 {
  font-size: 18px;
}

h3 {
  font-size: 16px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 20px;
  max-width: 1240px;
  margin: 0 auto;
  align-items: start;
}

.panel {
  background: #ffffff;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgb(37 55 84 / 8%);
}

.file-panel,
.chat-panel {
  padding: 20px;
}

.panel-heading,
.section-title,
.reference-head,
.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.panel-heading {
  margin-bottom: 18px;
}

.panel-heading p {
  margin-top: 6px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.5;
}

.upload-box {
  display: grid;
  gap: 8px;
  padding: 18px;
  border: 1px dashed #9bb2ce;
  border-radius: 8px;
  background: #f8fbff;
  cursor: pointer;
}

.upload-box input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.upload-title {
  color: #172033;
  font-weight: 700;
  word-break: break-word;
}

.upload-meta,
.file-main span,
.section-title span,
.form-actions span,
.file-status small,
.reference-list small {
  color: #64748b;
  font-size: 13px;
}

.primary-button,
.ghost-button {
  min-height: 40px;
  border: 0;
  border-radius: 6px;
  padding: 0 16px;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  width: 100%;
  margin-top: 12px;
  background: #1f6feb;
  color: #ffffff;
}

.ghost-button {
  background: #ffffff;
  color: #1f6feb;
  border: 1px solid #b7c7dc;
}

.primary-button:disabled,
.ghost-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.notice {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.5;
}

.success {
  color: #17633a;
  background: #e8f7ee;
}

.error,
.error-text {
  color: #b42318;
}

.error {
  background: #fff0ed;
}

.section-title {
  margin: 22px 0 12px;
}

.state,
.answer-state {
  border: 1px solid #e1e8f2;
  border-radius: 8px;
  padding: 18px;
  color: #64748b;
  background: #fbfdff;
  text-align: center;
}

.error-state {
  color: #b42318;
  background: #fff8f6;
}

.file-list,
.reference-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.file-list {
  display: grid;
  gap: 10px;
}

.file-item {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid #e1e8f2;
  border-radius: 8px;
}

.file-main {
  display: grid;
  gap: 5px;
}

.file-main strong {
  word-break: break-word;
}

.file-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.status-pill,
.session-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: 999px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 800;
}

.status-UPLOADED {
  color: #475569;
  background: #eef2f7;
}

.status-PROCESSING {
  color: #865503;
  background: #fff3d6;
}

.status-SUCCESS {
  color: #17633a;
  background: #def7e9;
}

.status-FAILED {
  color: #b42318;
  background: #ffe4df;
}

.session-chip {
  color: #1f6feb;
  background: #e8f1ff;
}

.file-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
}

.ask-form {
  display: grid;
  gap: 12px;
}

textarea {
  width: 100%;
  min-height: 128px;
  box-sizing: border-box;
  resize: vertical;
  border: 1px solid #cbd6e4;
  border-radius: 8px;
  padding: 14px;
  color: #172033;
  font: inherit;
  line-height: 1.6;
}

textarea:focus {
  outline: 2px solid #b7d4ff;
  border-color: #1f6feb;
}

.form-actions .primary-button {
  width: auto;
  min-width: 108px;
  margin-top: 0;
}

.answer-state {
  margin-top: 18px;
}

.answer {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.question-line,
.answer-line {
  display: grid;
  gap: 8px;
}

.question-line span,
.answer-line span {
  color: #4d627d;
  font-size: 13px;
  font-weight: 800;
}

.answer-line p {
  padding: 16px;
  border-radius: 8px;
  background: #f7fafc;
  line-height: 1.8;
  white-space: pre-wrap;
}

.reference-list {
  display: grid;
  gap: 12px;
  counter-reset: references;
}

.reference-list li {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #e1e8f2;
  border-radius: 8px;
  background: #ffffff;
}

.reference-head strong {
  word-break: break-word;
}

.reference-head span {
  color: #1f6feb;
  font-size: 13px;
  font-weight: 800;
}

.reference-list p {
  color: #334155;
  line-height: 1.7;
}

@media (max-width: 900px) {
  .workspace {
    padding: 20px;
  }

  .topbar,
  .layout {
    display: grid;
    grid-template-columns: 1fr;
  }

  .topbar {
    align-items: start;
  }

  .ghost-button {
    width: 100%;
  }
}

@media (max-width: 560px) {
  .workspace {
    padding: 14px;
  }

  h1 {
    font-size: 24px;
  }

  .file-panel,
  .chat-panel {
    padding: 16px;
  }

  .panel-heading,
  .section-title,
  .file-status,
  .form-actions,
  .reference-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .form-actions .primary-button {
    width: 100%;
  }
}
</style>
