<script setup>

import { ref } from 'vue'

import { onShow } from '@dcloudio/uni-app'

import { crmApi } from '@/utils/api'

import { ensureSession } from '@/utils/session'

import { hasPermission } from '@/utils/permissions'

import { usePagedList } from '@/utils/usePagedList'



const { loading, loadingMore, items, total, hasMore, loadFirst, loadMore } = usePagedList(

  (page, pageSize) => crmApi.listTasks({ page, page_size: pageSize, status: 'open' }),

  20,

)



const permissions = ref([])



const canEdit = () => hasPermission(permissions.value, 'crm.task.edit')



async function loadData() {

  try {

    const user = await ensureSession()

    permissions.value = user?.permissions || []

    await loadFirst()

  } catch (e) {

    uni.showToast({ title: e.message || '加载失败', icon: 'none' })

  }

}



async function markDone(item) {

  if (!canEdit()) return

  try {

    await crmApi.updateTask(item.id, { status: 'done' })

    uni.showToast({ title: '已完成', icon: 'success' })

    await loadData()

  } catch (e) {

    uni.showToast({ title: e.message || '失败', icon: 'none' })

  }

}



onShow(loadData)

</script>



<template>

  <view class="page">

    <view class="hero">

      <text class="hero__sub">{{ loading ? '加载中…' : `共 ${total} 条待办` }}</text>

    </view>



    <scroll-view scroll-y class="scroll" :lower-threshold="100" @scrolltolower="loadMore">

      <view v-if="loading" class="empty">加载中…</view>

      <view v-else-if="!items.length" class="empty">暂无待办任务</view>

      <view v-else class="list">

        <view v-for="item in items" :key="item.id" class="card">

          <text class="card__title">{{ item.title }}</text>

          <text class="card__meta">{{ item.due_at ? item.due_at.slice(0, 16) : '无截止' }}</text>

          <view v-if="canEdit()" class="card__acts">

            <text class="link" @click="markDone(item)">标记完成</text>

          </view>

        </view>

        <view v-if="loadingMore" class="list-foot">加载中…</view>

        <view v-else-if="!hasMore && items.length" class="list-foot">没有更多了</view>

      </view>

    </scroll-view>

  </view>

</template>



<style scoped>

.page {

  height: 100vh;

  display: flex;

  flex-direction: column;

  background: #f5f5f5;

  padding: 12px;

  box-sizing: border-box;

}



.hero {

  margin-bottom: 12px;

  flex-shrink: 0;

}



.hero__sub {

  color: #64748b;

  font-size: 13px;

}



.scroll {

  flex: 1;

  min-height: 0;

}



.list {

  display: flex;

  flex-direction: column;

  gap: 10px;

}



.card {

  background: #fff;

  border-radius: 10px;

  padding: 14px;

}



.card__title {

  font-size: 16px;

  font-weight: 600;

  display: block;

}



.card__meta {

  color: #64748b;

  font-size: 13px;

  margin-top: 6px;

  display: block;

}



.card__acts {

  margin-top: 10px;

}



.link {

  color: #1677ff;

  font-size: 14px;

}



.empty {

  text-align: center;

  color: #94a3b8;

  padding: 40px 0;

}



.list-foot {

  text-align: center;

  color: #94a3b8;

  font-size: 13px;

  padding: 16px 0;

}

</style>

