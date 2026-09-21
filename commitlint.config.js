// 格式：<emoji> type(scope): subject
// type 为标准 Conventional Commits 类型，每个 type 对应唯一 emoji（1:1）。
// emoji 仅作视觉前缀，校验与 changelog/语义化版本仍以 Conventional type 为准。

const norm = (s) => s?.replace(/️/g, '').trim() ?? '';

// Conventional type → 唯一 emoji（与 cz-conventional-gitmoji 习惯一致）
const TYPE_EMOJI = {
  feat: ['✨'],     // 新功能
  fix: ['🐛'],      // 缺陷修复
  docs: ['📝'],     // 文档
  style: ['🎨'],    // 代码风格 / 格式（不改语义）
  refactor: ['♻️'], // 重构
  perf: ['⚡️'],    // 性能
  test: ['✅'],     // 测试
  build: ['📦️'],   // 构建系统 / 外部依赖
  ci: ['👷'],       // CI 配置与脚本
  chore: ['🔧'],    // 杂务 / 工具 / 配置
  revert: ['⏪️'],  // 回滚提交
};

module.exports = {
  parserPreset: {
    parserOpts: {
      headerPattern:
        /^([\u{1F000}-\u{1FAFF}\u{2300}-\u{2BFF}]️?)\s([\w-]+)(?:\((\S+)\))?!?:\s(.+)/u,
      headerCorrespondence: ['emoji', 'type', 'scope', 'subject'],
    },
  },
  plugins: [
    {
      rules: {
        'emoji-type-match': ({ emoji, type }) => {
          const allowed = TYPE_EMOJI[type];
          if (!allowed) return [true];
          const ok = allowed.map(norm).includes(norm(emoji));
          return [
            ok,
            `"${emoji}" 与 type "${type}" 不匹配，应为: ${allowed[0]}`,
          ];
        },
      },
    },
  ],
  rules: {
    'emoji-type-match': [2, 'always'],
    'type-enum': [2, 'always', Object.keys(TYPE_EMOJI)],
    'type-empty': [2, 'never'],
    'scope-case': [2, 'always', 'lower-case'],
    'subject-empty': [2, 'never'],
    'subject-case': [0],
    'header-max-length': [2, 'always', 72],
    'body-leading-blank': [1, 'always'],
    'footer-leading-blank': [1, 'always'],
  },
};
