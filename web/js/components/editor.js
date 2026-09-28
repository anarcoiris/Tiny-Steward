/**
 * File Explorer & Light Code Editor Component - Full CRUD and Shortcuts.
 */

import { fetchFileTree, fetchFileContent, saveFileContent, createFile, deleteFile } from '../api.js';
import { showPromptModal, showConfirmModal } from '../modal.js';

export function initEditorComponent(AppState) {
  const treeContainer = document.getElementById('file-tree-container');
  const editorTitle = document.getElementById('editor-file-title');
  const codeArea = document.getElementById('code-textarea');
  const saveBtn = document.getElementById('save-file-btn');
  const treePanel = document.querySelector('.file-tree-panel');

  if (!treeContainer || !codeArea) return;

  let currentPath = null;
  let isDirty = false;

  // Add toolbar above file tree if not already present
  if (treePanel && !treePanel.querySelector('.file-tree-toolbar')) {
    const toolbar = document.createElement('div');
    toolbar.className = 'file-tree-toolbar';
    toolbar.style.display = 'flex';
    toolbar.style.gap = '6px';
    toolbar.style.marginBottom = '10px';

    toolbar.innerHTML = `
      <button id="btn-new-file" class="btn btn-secondary" style="font-size:0.75rem; padding:3px 7px;" title="Nuevo Archivo">📄 +</button>
      <button id="btn-new-folder" class="btn btn-secondary" style="font-size:0.75rem; padding:3px 7px;" title="Nueva Carpeta">📁 +</button>
      <button id="btn-delete-file" class="btn btn-secondary" style="font-size:0.75rem; padding:3px 7px; color:var(--accent-rose);" title="Eliminar">🗑️</button>
      <button id="btn-refresh-tree" class="btn btn-secondary" style="font-size:0.75rem; padding:3px 7px;" title="Recargar">🔄</button>
    `;

    treePanel.insertBefore(toolbar, treeContainer);

    document.getElementById('btn-new-file')?.addEventListener('click', promptNewFile);
    document.getElementById('btn-new-folder')?.addEventListener('click', promptNewFolder);
    document.getElementById('btn-delete-file')?.addEventListener('click', promptDeleteFile);
    document.getElementById('btn-refresh-tree')?.addEventListener('click', loadTree);
  }

  async function loadTree() {
    treeContainer.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem;">Cargando archivos...</div>';
    try {
      const treeData = await fetchFileTree();
      renderTree(treeData, treeContainer);
    } catch (err) {
      treeContainer.innerHTML = `<div style="color:var(--accent-rose); font-size:0.8rem;">Error al cargar árbol: ${err.message}</div>`;
    }
  }

  function renderTree(nodes, parentEl) {
    parentEl.innerHTML = '';
    nodes.forEach(node => {
      const itemEl = document.createElement('div');
      itemEl.className = 'file-tree-node';
      itemEl.dataset.path = node.path;
      itemEl.style.cursor = 'pointer';
      itemEl.style.userSelect = 'none';
      itemEl.innerHTML = `${node.is_dir ? '📁' : '📄'} ${node.name}`;
      
      if (!node.is_dir) {
        itemEl.addEventListener('click', (e) => {
          e.stopPropagation();
          openFile(node.path, itemEl);
        });
      } else if (node.children && node.children.length > 0) {
        const subContainer = document.createElement('div');
        subContainer.style.paddingLeft = '14px';
        renderTree(node.children, subContainer);
        itemEl.appendChild(subContainer);

        itemEl.addEventListener('click', (e) => {
          if (e.target === itemEl || e.target.firstChild === itemEl.firstChild) {
            e.stopPropagation();
            subContainer.style.display = subContainer.style.display === 'none' ? 'block' : 'none';
            currentPath = node.path;
            if (editorTitle) editorTitle.textContent = `📁 ${node.path}`;
          }
        });
      }
      
      parentEl.appendChild(itemEl);
    });
  }

  async function openFile(filePath, nodeEl) {
    if (isDirty && currentPath) {
      const confirmLeave = await showConfirmModal('Cambios no guardados', `¿Deseas descartar los cambios en ${currentPath}?`);
      if (!confirmLeave) return;
    }

    document.querySelectorAll('.file-tree-node').forEach(el => el.classList.remove('selected'));
    if (nodeEl) nodeEl.classList.add('selected');

    currentPath = filePath;
    isDirty = false;
    if (editorTitle) editorTitle.textContent = filePath;
    codeArea.value = 'Cargando contenido del archivo...';

    try {
      const res = await fetchFileContent(filePath);
      codeArea.value = res.content;
    } catch (err) {
      codeArea.value = `Error al abrir archivo: ${err.message}`;
    }
  }

  async function saveCurrent() {
    if (!currentPath) return;
    if (saveBtn) saveBtn.disabled = true;
    try {
      await saveFileContent(currentPath, codeArea.value);
      isDirty = false;
      if (editorTitle) editorTitle.textContent = currentPath;
      if (saveBtn) {
        saveBtn.textContent = '✅ Guardado';
        setTimeout(() => { saveBtn.textContent = 'Guardar'; saveBtn.disabled = false; }, 1400);
      }
    } catch (err) {
      alert(`Error al guardar archivo: ${err.message}`);
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  async function promptNewFile() {
    const filePath = await showPromptModal('Crear Nuevo Archivo', 'ej: scripts/mi_script.py');
    if (!filePath || !filePath.trim()) return;
    try {
      await createFile(filePath.trim(), false, '');
      await loadTree();
      openFile(filePath.trim(), null);
    } catch (err) {
      alert(`Error al crear archivo: ${err.message}`);
    }
  }

  async function promptNewFolder() {
    const dirPath = await showPromptModal('Crear Nueva Carpeta', 'ej: scripts/helpers');
    if (!dirPath || !dirPath.trim()) return;
    try {
      await createFile(dirPath.trim(), true, '');
      await loadTree();
    } catch (err) {
      alert(`Error al crear directorio: ${err.message}`);
    }
  }

  async function promptDeleteFile() {
    if (!currentPath) {
      alert('Por favor selecciona un archivo o carpeta en el árbol.');
      return;
    }
    const confirmDel = await showConfirmModal('Eliminar Archivo / Directorio', `¿Estás seguro de que deseas eliminar permanentemente: ${currentPath}?`);
    if (!confirmDel) return;

    try {
      await deleteFile(currentPath);
      currentPath = null;
      if (editorTitle) editorTitle.textContent = 'Ningún archivo seleccionado';
      codeArea.value = '';
      await loadTree();
    } catch (err) {
      alert(`Error al eliminar: ${err.message}`);
    }
  }

  codeArea.addEventListener('input', () => {
    if (!isDirty && currentPath) {
      isDirty = true;
      if (editorTitle) editorTitle.textContent = `${currentPath} *`;
    }
  });

  // Ctrl+S / Cmd+S shortcut
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      const activeEl = document.activeElement;
      if (activeEl === codeArea || document.getElementById('tab-editor')?.classList.contains('active')) {
        e.preventDefault();
        saveCurrent();
      }
    }
  });

  if (saveBtn) {
    saveBtn.addEventListener('click', saveCurrent);
  }

  loadTree();
}
