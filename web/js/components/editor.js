/**
 * File Explorer & Light Code Editor Component.
 */

import { fetchFileTree, fetchFileContent, saveFileContent } from '../api.js';

export function initEditorComponent(AppState) {
  const treeContainer = document.getElementById('file-tree-container');
  const editorTitle = document.getElementById('editor-file-title');
  const codeArea = document.getElementById('code-textarea');
  const saveBtn = document.getElementById('save-file-btn');

  if (!treeContainer || !codeArea) return;

  let currentPath = null;

  async function loadTree() {
    try {
      const treeData = await fetchFileTree();
      renderTree(treeData, treeContainer);
    } catch (err) {
      treeContainer.innerHTML = `<div style="color:var(--accent-rose)">Failed to load file tree: ${err.message}</div>`;
    }
  }

  function renderTree(nodes, parentEl) {
    parentEl.innerHTML = '';
    nodes.forEach(node => {
      const itemEl = document.createElement('div');
      itemEl.className = 'file-tree-node';
      itemEl.innerHTML = `${node.is_dir ? '📁' : '📄'} ${node.name}`;
      
      if (!node.is_dir) {
        itemEl.addEventListener('click', () => openFile(node.path, itemEl));
      } else if (node.children && node.children.length > 0) {
        const subContainer = document.createElement('div');
        subContainer.style.paddingLeft = '14px';
        renderTree(node.children, subContainer);
        itemEl.appendChild(subContainer);
      }
      
      parentEl.appendChild(itemEl);
    });
  }

  async function openFile(filePath, nodeEl) {
    document.querySelectorAll('.file-tree-node').forEach(el => el.classList.remove('selected'));
    if (nodeEl) nodeEl.classList.add('selected');

    currentPath = filePath;
    if (editorTitle) editorTitle.textContent = filePath;
    codeArea.value = 'Loading file content...';

    try {
      const res = await fetchFileContent(filePath);
      codeArea.value = res.content;
    } catch (err) {
      codeArea.value = `Error loading file: ${err.message}`;
    }
  }

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      if (!currentPath) return;
      saveBtn.disabled = true;
      try {
        await saveFileContent(currentPath, codeArea.value);
        saveBtn.textContent = 'Saved!';
        setTimeout(() => { saveBtn.textContent = 'Save File'; saveBtn.disabled = false; }, 1500);
      } catch (err) {
        alert(`Error saving file: ${err.message}`);
        saveBtn.disabled = false;
      }
    });
  }

  loadTree();
}
