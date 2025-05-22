// main.js - 量化助手Web端主交互脚本

document.addEventListener('DOMContentLoaded', function() {
  // 持仓信息保存
  document.getElementById('save-pos-btn').onclick = function() {
    const data = {
      total_usdt: document.getElementById('total_usdt').value,
      pos_percent: document.getElementById('pos_percent').value,
      direction: document.getElementById('direction').value,
      open_price: document.getElementById('open_price').value,
      stop_loss: document.getElementById('stop_loss').value,
      is_empty: document.getElementById('empty_pos').checked
    };
    fetch('/api/position', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(r=>r.json()).then(res=>{
      alert(res.msg||'保存成功');
    });
  };

  // 获取指标及宏观因子采集结果
  document.getElementById('fetch-indicators-btn').onclick = function() {
    fetch('/api/indicators').then(r=>r.json()).then(data=>{
      document.getElementById('json-output').textContent = JSON.stringify(data, null, 2);
    });
  };

  // 图片上传与预览
  const imgInput = document.getElementById('image-input');
  const previewImg = document.getElementById('preview-img');
  imgInput.onchange = function() {
    if (imgInput.files && imgInput.files[0]) {
      const reader = new FileReader();
      reader.onload = function(e) {
        previewImg.src = e.target.result;
        previewImg.style.display = 'block';
      };
      reader.readAsDataURL(imgInput.files[0]);
    }
  };
  document.getElementById('upload-img-btn').onclick = function() {
    if (!imgInput.files || !imgInput.files[0]) {
      alert('请先选择图片');
      return;
    }
    const formData = new FormData();
    formData.append('image', imgInput.files[0]);
    fetch('/api/upload_image', {
      method: 'POST',
      body: formData
    }).then(r=>r.json()).then(res=>{
      alert(res.msg||'上传成功');
    });
  };

  // Gemini操作建议
  document.getElementById('gemini-advice-btn').onclick = function() {
    document.getElementById('gemini-advice-output').textContent = '正在请求Gemini建议...';
    fetch('/api/gemini_advice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    }).then(r=>r.json()).then(res=>{
      document.getElementById('gemini-advice-output').textContent = res.msg||'（接口待实现）';
    });
  };
});
