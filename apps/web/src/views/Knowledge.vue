<script setup>
const documents = [
  { name: '公司服务价目表.pdf', size: '256 KB', status: '已解析', chunks: 12 },
  { name: '财税FAQ.txt', size: '48 KB', status: '已解析', chunks: 8 },
  { name: '2026年申报节点.md', size: '32 KB', status: '解析中', chunks: 0 },
]
</script>

<template>
  <div class="knowledge-page">
    <div class="page-card">
      <div class="knowledge-page__header">
        <div class="page-title">知识库</div>
        <el-button type="primary" icon="Upload">上传文档</el-button>
      </div>
      <el-alert
        title="租户私有知识库优先于平台行业库，用于 AI 生成时 RAG 检索引用。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-table :data="documents" stripe>
        <el-table-column prop="name" label="文件名" min-width="200" />
        <el-table-column prop="size" label="大小" width="100" />
        <el-table-column prop="chunks" label="分块数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === '已解析' ? 'success' : 'warning'"
              size="small"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default>
            <el-button type="danger" link size="small">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.knowledge-page__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.knowledge-page__header .page-title {
  margin-bottom: 0;
}
</style>
