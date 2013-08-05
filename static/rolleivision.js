var submit = function(args, origin) {
  XHR.get('/rolleicom', args, function(x, r) {
    var success = r.response[0],
        value = r.response[1],
        status = r.response[2];
    var res = document.getElementById('res');
    var err = document.getElementById('error');
    if (success) {
      res.innerHTML = status + ' response';
      err.innerHTML = '';
    } else {
      err.innerHTML = 'error: ' + status;
      res.innerHTML = '';
    }
    if (typeof(value) === 'boolean') {
      if (value === true) {
        origin.classList.add('on');
      } else {
        origin.classList.remove('on');
      }
    }
  });
};

function formsend(form) {
  var query = {};
  for (var n = 0; n < form.elements.length; n++) {
    var field = form.elements[n];
    if (!field.hasAttribute('name') ||
        (/^(?:radio|checkbox)$/.test(field.type) && !field.checked)) {
              continue;
            }
    if (field.type === 'number' && isNaN(parseFloat(field.value))) {
      continue;
    }
    query[escape(field.getAttribute('name'))] = escape(field.value);
  }
  if (Object.keys(query).length > 0) {
    query['action'] = form.name;
    submit(query);
  }
  return false;
}

var throttle = function(func, wait) {
  var timeout;
  return function() {
    var context = this, args = arguments;
    if (!timeout) {
      // the first time the event fires, we setup a timer, which
      // is used as a guard to block subsequent calls; once the
      // timer's handler fires, we reset it and create a new one
      timeout = setTimeout(function() {
        timeout = null;
        func.apply(context, args);
      }, wait);
    }
  };
};

function toggleDark() {
    document.body.classList.toggle('dark');
}

var toggleLamps = function(origin) {
  XHR.get('/rolleicom', {'action': 'querylamps'}, function(x, r) {
    var emitting = r.response[1];
    if (emitting) {
      submit({'action': 'lampcontrol', 'wait': true}, origin);
      origin.classList.remove('on');
    } else {
      submit({'action': 'lampcontrol', 'left': 1, 'right': 1}, origin);
      origin.classList.add('on');
    }
  });
};
var setLeftBrightness = function(value) {
  submit({'action': 'brightnessleft', 'brightness': value}, this);
  document.getElementById('bleftvalue').value =
    ('\xA0\xA0\xA0\xA0\xA0' + (value / 255 * 100).toFixed(1)).slice(-5);
};

var setRightBrightness = function(value) {
  submit({'action': 'brightnessright', 'brightness': value}, this);
  document.getElementById('brightvalue').value =
    ('\xA0\xA0\xA0\xA0\xA0' + (value / 255 * 100).toFixed(1)).slice(-5);
};

var setDissolveTime = function(value) {
  submit({'action': 'dissolvefor', 'duration': value}, this);
  document.getElementById('dissolvevalue').value =
    ('\xA0\xA0\xA0' + (value / 10).toFixed(1)).slice(-5) + ' Sek.';
};

var sendBatch = function() {
    var batchentry = document.getElementById('batchentry');
    var runbatch = document.getElementById('runbatch');
    var resetbatch = document.getElementById('resetbatch');
    var closebatch = document.getElementById('closebatch');
    var script = batchentry.innerText;
    batchentry.innerHTML = '<span style="color:crimson;font-weight:bold;">Batch in progress ...</span>';
    batchentry.classList.add('invalid');
    runbatch.disabled = true;
    resetbatch.disabled = true;
    closebatch.disabled = true;

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/rolleicom', true);
    xhr.setRequestHeader('Content-type', 'text/plain');
    xhr.onload = function(e) {
        if (this.status == 200) {
            var json = eval('(' + this.responseText + ')');
            var success = json.response[0],
            value = json.response[1],
            status = json.response[2];
            console.log(status);
            batchentry.innerHTML = value;
            runbatch.disabled = false;
            resetbatch.disabled = false;
            closebatch.disabled = false;
            (success) ?
              batchentry.classList.remove('invalid') :
              batchentry.classList.add('invalid');
        }
    };

    xhr.send(script);
    return false;
};

var resetBatch = function() {
    XHR.get('/rolleicom', {'action': 'getbatch', 'default': 1}, function(x, r) {
        document.getElementById('batchentry').innerHTML = r.response[1];
    });
};

var checkConnection = function() {
  XHR.poll(5, '/rolleicom', {'action': 'connected'}, function(x, r) {
    var response = r.response;
    if (response) {
      document.getElementById('projector_status_online').style.display = '';
      document.getElementById('projector_status_offline').style.display = 'none';
    } else {
      document.getElementById('projector_status_online').style.display = 'none';
      document.getElementById('projector_status_offline').style.display = '';
    }
  });
};

var pollStatus = function() {
  XHR.poll(1, '/rolleicom', {'action': 'getstatus', 'verbose': true}, function(x, r) {
    document.getElementById('res').innerHTML = r.response + ' now';
  });
};

Mousetrap.bind(['?'], function(e) {
  document.getElementById('shortcuthelp').classList.toggle('hidden');
  return false;
});

Mousetrap.bind(['<'], function(e) {
  submit({'action': 'next'}, document.getElementById('forward'));
  return false;
});

Mousetrap.bind(['<'], function(e) {
  submit({'action': 'next'});
  return false;
});

Mousetrap.bind(['>'], function(e) {
  submit({'action': 'previous'});
  return false;
});

Mousetrap.bind(['e'], function(e) {
  submit({'action': 'end'});
  return false;
});

Mousetrap.bind(['r'], function(e) {
  submit({'action': 'reset'});
  return false;
});

Mousetrap.bind(['p'], function(e) {
  submit({'action': 'togglePC'}, document.getElementById('pcmode'));
  return false;
});

Mousetrap.bind(['s'], function(e) {
  submit({'action': 'togglestop'});
  return false;
});

Mousetrap.bind(['b'], function(e) {
  document.getElementById('batchpopup').classList.toggle('hidden');
  return false;
});

Mousetrap.bind(['+'], function(e) {
  submit({'action': 'focusin'});
  return false;
});

Mousetrap.bind(['-'], function(e) {
  submit({'action': 'focusout'});
  return false;
});

Mousetrap.bind(['h'], function(e) {
  var element = document.getElementById('bleftinput');
  element.stepDown(10);
  var evt = document.createEvent('HTMLEvents');
  evt.initEvent('change', false, true);
  element.dispatchEvent(evt);
  return false;
});

Mousetrap.bind(['j'], function(e) {
  var element = document.getElementById('bleftinput');
  element.stepUp(10);
  var evt = document.createEvent('HTMLEvents');
  evt.initEvent('change', false, true);
  element.dispatchEvent(evt);
  return false;
});

Mousetrap.bind(['k'], function(e) {
  var element = document.getElementById('brightinput');
  element.stepDown(10);
  var evt = document.createEvent('HTMLEvents');
  evt.initEvent('change', false, true);
  element.dispatchEvent(evt);
  return false;
});

Mousetrap.bind(['l'], function(e) {
  var element = document.getElementById('brightinput');
  element.stepUp(10);
  var evt = document.createEvent('HTMLEvents');
  evt.initEvent('change', false, true);
  element.dispatchEvent(evt);
  return false;
});

Mousetrap.bind(['a'], function(e) {
  var element = document.getElementById('dissolveinput');
  element.stepDown(5);
  var evt = document.createEvent('HTMLEvents');
  evt.initEvent('change', false, true);
  element.dispatchEvent(evt);
  return false;
});

Mousetrap.bind(['y'], function(e) {
  var element = document.getElementById('dissolveinput');
  element.stepUp(5);
  var evt = document.createEvent('HTMLEvents');
  evt.initEvent('change', false, true);
  element.dispatchEvent(evt);
  return false;
});

Mousetrap.bind(['1'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:200'});
  document.getElementById('leftlamp').classList.add('on');
});

Mousetrap.bind(['2'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:201'});
  document.getElementById('rightlamp').classList.add('on');
});

Mousetrap.bind(['3'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:202'});
  document.getElementById('leftlamp').classList.remove('on');
});

Mousetrap.bind(['4'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:203'});
  document.getElementById('rightlamp').classList.remove('on');
});

Mousetrap.bind(['5'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:204'});
  document.getElementById('leftlamp').classList.add('on');
  document.getElementById('rightlamp').classList.remove('on');
});

Mousetrap.bind(['6'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:205'});
  document.getElementById('rightlamp').classList.add('on');
  document.getElementById('leftlamp').classList.remove('on');
});

Mousetrap.bind(['7'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:206'});
  document.getElementById('leftlamp').classList.add('on');
  document.getElementById('rightlamp').classList.add('on');
});

Mousetrap.bind(['8'], function(e) {
  submit({'action': 'submit', 'cmd': 'LM:207'});
  document.getElementById('leftlamp').classList.remove('on');
  document.getElementById('rightlamp').classList.remove('on');
});

// Suspend XHR requests when tab is not visible
(function() {
  var hidden = 'hidden';

  if (hidden in document)
    document.addEventListener('visibilitychange', onchange);
  else if ((hidden = 'mozHidden') in document)
    document.addEventListener('mozvisibilitychange', onchange);
  else if ((hidden = 'webkitHidden') in document)
    document.addEventListener('webkitvisibilitychange', onchange);

  function onchange(evt) {
    if (document[hidden]) {
      XHR.halt();
    } else {
      XHR.run();
    }
  }
})();

window.onload = function() {
  var bleft = document.getElementById('bleftinput'),
  bright = document.getElementById('brightinput'),
  lleft = document.getElementById('lleftinput'),
  lright = document.getElementById('lrightinput'),
  dissolve = document.getElementById('dissolveinput'),
  pcmode = document.getElementById('pcmode'),
  stopgo = document.getElementById('stopgo'),
  autofocus = document.getElementById('autofocus');
  lamps = document.getElementById('lamps');

  bleft.addEventListener('change', throttle(function() {
    setLeftBrightness(bleft.value)}, 50), false);
  bright.addEventListener('change', throttle(function() {
    setRightBrightness(bright.value)}, 50), false);
  dissolve.addEventListener('change', throttle(function() {
    setDissolveTime(dissolve.value)}, 250), false);

  var initBatch = function() {
    XHR.get('/rolleicom', {'action': 'getbatch'}, function(x, r) {
      document.getElementById('batchentry').innerHTML = r.response[1];
    });
  };
  initBatch();
  var initStopped = function() {
    XHR.get('/rolleicom', {'action': 'querystopped'}, function(x, r) {
      var value = r.response[1];
      if (value === true) {
        stopgo.classList.add('on');
      } else {
        stopgo.classList.remove('on');
      }
      //checkConnection();
      //pollStatus();
      initBatch();
    });
  };
  var initPCmode = function() {
    XHR.get('/rolleicom', {'action': 'queryPCmode'}, function(x, r) {
      var value = r.response[1];
      if (value === true) {
        pcmode.classList.add('on');
      } else {
        pcmode.classList.remove('on');
      }
      initStopped();
    });
  };
  var initAF = function() {
    XHR.get('/rolleicom', {'action': 'queryAF'}, function(x, r) {
      var value = r.response[1];
      if (value === true) {
        autofocus.classList.add('on');
      } else {
        autofocus.classList.remove('on');
      }
      initPCmode();
    });
  };
  var initLamps = function() {
    XHR.get('/rolleicom', {'action': 'querylamps'}, function(x, r) {
      var value = r.response[1];
      if (value === true) {
        lamps.classList.add('on');
      } else {
        lamps.classList.remove('on');
      }
      initAF();
    });
  };
  var initDissolve = function() {
    XHR.get('/rolleicom', {'action': 'querydissolve'}, function(x, r) {
      var success = r.response[0],
          value = r.response[1],
          status = r.response[2];
      if (success) {
        dissolve.value = value;
        document.getElementById('dissolvevalue').value =
          ('\xA0\xA0\xA0' + (value / 10).toFixed(1)).slice(-5) + ' Sek.';
      }
      initLamps();
    });
  };
  var initLoaded = function() {
    XHR.get('/rolleicom', {'action': 'queryloaded'}, function(x, r) {
      var success = r.response[0],
          value = r.response[1],
          status = r.response[2];
      if (success) {
        lleft.value = value[0];
        lright.value = value[1];
      }
      initDissolve();
    });
  };
  var initBrightness = function() {
    XHR.get('/rolleicom', {'action': 'querybrightness'}, function(x, r) {
      var success = r.response[0],
          value = r.response[1],
          status = r.response[2];
      if (success) {
        bright.value = value[1];
        bleft.value = value[0];
        document.getElementById('brightvalue').value =
          ('\xA0\xA0\xA0\xA0\xA0' + (bright.value / 255 * 100).toFixed(1)).slice(-5);
        document.getElementById('bleftvalue').value =
          ('\xA0\xA0\xA0\xA0\xA0' + (bleft.value / 255 * 100).toFixed(1)).slice(-5);
      }
      initLoaded();
    });
  };
  var initConnection = function() {
    XHR.get('/rolleicom', {'action': 'connected'}, function(x, r) {
      var response = r.response;
      if (response) {
        document.getElementById('projector_status_online').style.display = '';
        document.getElementById('projector_status_offline').style.display = 'none';
      } else {
        document.getElementById('projector_status_online').style.display = 'none';
        document.getElementById('projector_status_offline').style.display = '';
      }
      initBrightness();
    });
  };

  initConnection();
};
