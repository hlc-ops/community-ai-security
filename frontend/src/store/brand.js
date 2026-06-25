import { defineStore } from 'pinia'
import axios from 'axios'

/** 品牌信息（系统名/副标题/logo），登录页和侧栏共用。
 *  应用启动时 fetchBrand() 一次；管理员改完触发 update() 刷新。 */
export const useBrandStore = defineStore('brand', {
  state: () => ({
    name: '工地安防预警系统',
    subtitle: '基于深度学习的智能工地安防违规识别平台',
    logoUrl: '',
    loaded: false,
  }),
  actions: {
    async fetchBrand() {
      try {
        const { data } = await axios.get('/api/settings/brand')
        const c = data.config || {}
        if (c.name) this.name = c.name
        if (c.subtitle) this.subtitle = c.subtitle
        if (c.logoUrl !== undefined) this.logoUrl = c.logoUrl
        this.loaded = true
        // 同步浏览器标签标题
        if (typeof document !== 'undefined' && c.name) {
          document.title = c.name
        }
      } catch (e) {
        /* 网络失败用默认值即可 */
      }
    },
    apply(cfg) {
      if (cfg.name) this.name = cfg.name
      if ('subtitle' in cfg) this.subtitle = cfg.subtitle
      if ('logoUrl' in cfg) this.logoUrl = cfg.logoUrl
      if (typeof document !== 'undefined' && this.name) document.title = this.name
    },
  },
})
