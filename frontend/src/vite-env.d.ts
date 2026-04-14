/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_API_TIMEOUT: string
  readonly VITE_AMAP_WEB_JS_KEY: string
  readonly VITE_AMAP_SECURITY_JS_CODE: string
  readonly VITE_AMAP_STATIC_KEY?: string
  readonly VITE_AMAP_STATIC_SIG?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
