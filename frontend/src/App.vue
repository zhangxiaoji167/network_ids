<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="app-aside">
      <div class="logo">
        <el-icon size="24"><Monitor /></el-icon>
        <span>入侵检测系统</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#001529"
        text-color="#ffffffa0"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>检测面板</span>
        </el-menu-item>
        <el-menu-item index="/model">
          <el-icon><TrendCharts /></el-icon>
          <span>模型评估</span>
        </el-menu-item>
        <el-menu-item index="/connections">
          <el-icon><List /></el-icon>
          <span>连接记录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <span class="page-title">{{ $route.meta.title }}</span>
        <el-tag type="success" size="small">系统运行中</el-tag>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.app-layout { height: 100vh; }
.app-aside { background: #001529; overflow: hidden; display: flex; flex-direction: column; }
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid #ffffff15;
  flex-shrink: 0;
}
.el-menu { border-right: none; flex: 1; }
.app-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.page-title { font-size: 16px; font-weight: 600; color: #262626; }
.app-main { padding: 24px; overflow-y: auto; }
</style>
