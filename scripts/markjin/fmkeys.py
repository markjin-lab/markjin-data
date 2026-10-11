"""front matter 分类键的唯一定义（整体验收 r10 BLOCKER，王总定）。

selfcheck（医疗 / 宏观 / 宗教置位）与 route（审批类型判定、未知类别须王总）共用这一份，不得各自维护。
键名大小写不敏感；新增分类键只改这里，两边同时生效（tests 断言两边引用同一对象）。"""

FM_CATEGORY_KEYS = frozenset({
    "categories", "category", "tags", "tag", "keywords", "keyword", "type", "series", "section", "sections",
    "topics", "topic", "kind", "subject", "subjects",
})
