# Taobao — Item SKU selection, cart, seller chat (PC web)

Field-tested against item.taobao.com / cart.taobao.com / market.m.taobao.com on 2026-10-09 with a logged-in Chrome session.
**Bot detection does trigger** (see Traps) — plan to hand SKU clicking to the user when you need more than a handful.

## URL patterns

- Item: `https://item.taobao.com/item.htm?id=<itemId>` (a `&skuId=` may get appended after you pick options).
- Search: `https://s.taobao.com/search?q=<urlencoded>` — item links are `a[href*="item.taobao.com"]` / `a[href*="detail.tmall.com"]`, `innerText` holds title + price + sales + shop in one string.
- Cart: `https://cart.taobao.com/cart.htm`
- Seller chat (旺旺 web): `https://market.m.taobao.com/app/im/chat/index.html?uid=<sellerUid>&type=web` — the message list is not in `document.body.innerText` of the top page; use screenshots.

## Item page (new React detail page)

- SKU option tiles: `div[class*="valueItem--"]`, label in `span[class*="valueItemText--"]`. Selected state = class contains `isSelected--`.
- **Clicking an already-selected tile deselects it.** Check `isSelected--` first and only click when not selected — otherwise you alternate between selected/unselected across a loop.
- Measure the tile rect *after* `scrollIntoView({block:"center", behavior:"instant"})` + a short wait; measuring before the scroll settles lands the click on the neighbouring tile.
- Buy bar: `div[class*="EmphasizeButtonList"] > div[class*="btnItem"]` — the **first** child is add-to-cart (icon `icon-taobaojiarugouwuche`, no text), the second is 立即购买/领券购买.
- After add-to-cart a dialog appears with the leaf text `成功加入购物车` and buttons `去购物车` / `继续购物`.
- Price block text looks like `平台加补后￥3.93优惠前￥5.8`; the low price often includes a one-time 首单礼金, so N items cost more than N × shown price.
- A first-visit tooltip (`div[class*="tipBtn"]`, text 知道了) can sit over the SKU area.
- Detail images (图文详情) are lazy: `img[src*="s.gif"]` with the real URL in `data-src` / `data-ks-lazyload`; fetch those directly instead of scrolling.

## Cart page

- Shop and item checkboxes are `label.ant-checkbox-wrapper`; checked ones also carry `ant-checkbox-wrapper-checked`.
- The right panel starting with `结算明细` lists 商品总价 / 官方立减 / 淘金币 / 首单礼金 / 合计 and the button `结算(N)` — read it to confirm what is selected before checkout.
- Per-item SKU text is in the row as `付款方式：… 校区：…` (seller-defined property names).

## Traps

- **Rapid SKU switching triggers a 拖图 captcha** ("将满足描述的所有图片拖放到指定区域后提交"). It appeared after ~15 add-to-cart cycles, and again within a few clicks on a fresh tab even with 4–7 s random pauses. Detection signals: overlay `#baxia-dialog-content`, an `iframe[src*=punish]`, or the tab URL switching to `…/_____tmd_____/…`. Do not try to solve it — stop and hand over.
- Chrome shows "自动测试软件正在控制 Chrome" while CDP is attached; Taobao evidently notices.
- `scroll()` on the IM page can time out the CDP call even though the scroll happens.
