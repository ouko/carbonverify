import { defineConfig, mergeConfig } from 'vite'
import { visualizer } from 'rollup-plugin-visualizer'
import baseConfig from './vite.config'

export default mergeConfig(
  baseConfig,
  defineConfig({
    plugins: [
      visualizer({
        open: true,
        gzipSize: true,
        brotliSize: true,
        filename: 'dist/stats.html',
      }),
    ],
  }),
)
