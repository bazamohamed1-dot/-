const sourceStr = `<div style="max-height: 200px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                    <div style="margin-bottom: 10px;">
                        <strong><i class="fas fa-utensils"></i> المطعم</strong>
                        <div style="margin-right: 15px;">
                             <div><input type="checkbox" class="perm-check" value="access_canteen" id="perm_canteen_access"> <label for="perm_canteen_access">الدخول للواجهة</label></div>
                        </div>
                    </div>
                </div>`;
const JSDOM = require("jsdom").JSDOM;
const dom = new JSDOM(`<!DOCTYPE html><html><body><div id="userModal">${sourceStr}</div><div id="rolePermsContainer"></div></body></html>`);
const document = dom.window.document;

const source = document.querySelector('#userModal .max-height-200, #userModal div[style*="max-height: 200px"]');
console.log(source);
