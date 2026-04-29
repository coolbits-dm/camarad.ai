(function () {
  var catalogPromise = null;
  var availabilityCache = {};

  function key(value) {
    return String(value || '').trim().toLowerCase();
  }

  function listProviders(catalog) {
    return Array.isArray(catalog && catalog.providers) ? catalog.providers : [];
  }

  function getAliasMap(catalog) {
    return (catalog && typeof catalog.provider_aliases === 'object' && catalog.provider_aliases) || {};
  }

  function getLegacyModelAliases(catalog) {
    return (catalog && typeof catalog.legacy_model_aliases === 'object' && catalog.legacy_model_aliases) || {};
  }

  function normalizeProvider(value, catalog) {
    var normalized = key(value);
    if (!normalized) return '';
    var aliases = getAliasMap(catalog);
    return aliases[normalized] || normalized;
  }

  function getProvider(catalog, providerValue) {
    var slug = normalizeProvider(providerValue, catalog);
    return listProviders(catalog).find(function (provider) {
      return provider && provider.slug === slug;
    }) || null;
  }

  function modelMatches(model, value) {
    var normalized = key(value);
    if (!model || !normalized) return false;
    if (key(model.id) === normalized) return true;
    if (key(model.label) === normalized) return true;
    if (key(model.provider_model_id) === normalized) return true;
    var aliases = Array.isArray(model.aliases) ? model.aliases : [];
    return aliases.some(function (alias) { return key(alias) === normalized; });
  }

  function inferProviderFromModel(catalog, modelValue) {
    var normalized = key(modelValue);
    if (!normalized) return '';
    var legacyAliases = getLegacyModelAliases(catalog);
    if (legacyAliases[normalized]) return legacyAliases[normalized];
    var providers = listProviders(catalog);
    for (var i = 0; i < providers.length; i += 1) {
      var provider = providers[i];
      var models = Array.isArray(provider && provider.models) ? provider.models : [];
      for (var j = 0; j < models.length; j += 1) {
        if (modelMatches(models[j], normalized)) {
          return provider.slug;
        }
      }
    }
    return '';
  }

  function findModel(catalog, providerSlug, modelValue) {
    var provider = getProvider(catalog, providerSlug);
    if (!provider) return null;
    var models = Array.isArray(provider.models) ? provider.models : [];
    var normalized = key(modelValue);
    if (!normalized) return null;
    return models.find(function (model) {
      return modelMatches(model, normalized);
    }) || null;
  }

  function buildProviderLabel(provider) {
    if (!provider) return '';
    var label = String(provider.label || provider.slug || 'Provider');
    var suffix = '';
    if (provider.status && provider.status !== 'live') {
      suffix = provider.status === 'beta' ? ' · beta' : ' · planned';
    }
    return label + suffix;
  }

  function buildModelLabel(model) {
    if (!model) return '';
    var label = String(model.label || model.id || 'Model');
    var flags = [];
    if (model._availability === 'live') flags.push('live');
    else if (model._availability === 'catalog') flags.push('catalog');
    else if (model._availability === 'unverified') flags.push('unverified');
    if (model.latest) flags.push('latest');
    if (model._uncuratedLive) flags.push('uncurated');
    return flags.length ? (label + ' · ' + flags.join(' · ')) : label;
  }

  function sortModels(models) {
    return (models || []).slice().sort(function (a, b) {
      var aLive = a && a._availability === 'live' ? 1 : 0;
      var bLive = b && b._availability === 'live' ? 1 : 0;
      if (aLive !== bLive) return bLive - aLive;
      var aLatest = a && a.latest ? 1 : 0;
      var bLatest = b && b.latest ? 1 : 0;
      if (aLatest !== bLatest) return bLatest - aLatest;
      return String(a && (a.label || a.id) || '').localeCompare(String(b && (b.label || b.id) || ''));
    });
  }

  function clearSelect(selectEl) {
    if (!selectEl) return;
    while (selectEl.firstChild) {
      selectEl.removeChild(selectEl.firstChild);
    }
  }

  function populateProviderSelect(selectEl, catalog, selectedProvider) {
    if (!selectEl) return;
    clearSelect(selectEl);
    var providers = listProviders(catalog);
    providers.forEach(function (provider) {
      var option = document.createElement('option');
      option.value = provider.slug;
      option.textContent = buildProviderLabel(provider);
      option.selected = provider.slug === selectedProvider;
      selectEl.appendChild(option);
    });
  }

  function availabilitySummaryText(provider, availability) {
    if (!provider && !availability) return '';
    var parts = [];
    if (provider && provider.notes) parts.push(String(provider.notes || '').trim());
    if (!availability) {
      parts.push('Checking live workspace availability...');
      return parts.join(' · ');
    }
    var mode = String(availability.credential_mode || 'none').trim();
    var liveCount = Array.isArray(availability.live_models) ? availability.live_models.length : 0;
    if (availability.status === 'active' || availability.status === 'validated') {
      parts.unshift(
        (mode === 'byok' ? 'BYOK' : mode === 'managed' ? 'Managed' : 'Credential')
        + ' validated'
        + (availability.validated_at ? (' ' + String(availability.validated_at).replace('T', ' ').replace('Z', ' UTC')) : '')
      );
      parts.push(String(liveCount) + ' live model' + (liveCount === 1 ? '' : 's') + ' returned.');
    } else if (availability.status === 'catalog_only') {
      parts.unshift('Catalog fallback only.');
      parts.push('Live provider listing is not wired for this provider yet.');
    } else if (availability.status === 'missing_credentials') {
      parts.unshift('No BYOK or managed credential detected for this provider.');
    } else if (availability.status === 'validation_failed') {
      parts.unshift('Provider validation failed.');
      if (availability.error && availability.error.message) {
        parts.push(String(availability.error.message));
      }
    } else {
      parts.unshift('Workspace availability not verified yet.');
    }
    return parts.join(' · ');
  }

  function mergeProviderModels(catalog, providerSlug, availability) {
    var provider = getProvider(catalog, providerSlug);
    var curated = Array.isArray(provider && provider.models) ? provider.models : [];
    var liveSet = new Set(
      ((availability && availability.live_models) || [])
        .map(function (modelId) { return String(modelId || '').trim(); })
        .filter(Boolean)
    );
    var seen = {};
    var curatedModels = sortModels(curated.map(function (model) {
      var item = Object.assign({}, model);
      item._availability = liveSet.has(String(item.id || '').trim()) ? 'live' : (availability ? 'catalog' : 'unverified');
      item._uncuratedLive = false;
      seen[key(item.id)] = true;
      return item;
    }));

    var liveOnlyModels = Array.from(liveSet)
      .filter(function (modelId) { return !seen[key(modelId)]; })
      .map(function (modelId) {
        return {
          id: modelId,
          label: modelId,
          latest: false,
          _availability: 'live',
          _uncuratedLive: true,
        };
      })
      .sort(function (a, b) {
        return String(a.label || a.id || '').localeCompare(String(b.label || b.id || ''));
      });

    return {
      curatedModels: curatedModels,
      liveOnlyModels: liveOnlyModels,
    };
  }

  function appendModelOptions(parentEl, models, resolvedValue) {
    (models || []).forEach(function (model) {
      var option = document.createElement('option');
      option.value = model.id;
      option.textContent = buildModelLabel(model);
      option.selected = model.id === resolvedValue;
      parentEl.appendChild(option);
    });
  }

  function populateModelSelect(config) {
    var selectEl = config && config.selectEl;
    var customInputEl = config && config.customInputEl;
    var helperEl = config && config.helperEl;
    var providerHelperEl = config && config.providerHelperEl;
    var catalog = config && config.catalog;
    var providerSlug = config && config.providerSlug;
    var selectedModel = config && config.selectedModel;
    var availability = config && config.availability;

    if (!selectEl) return { selectedModel: '', isCustom: false, availability: availability || null };

    clearSelect(selectEl);

    var provider = getProvider(catalog, providerSlug);
    var merged = mergeProviderModels(catalog, providerSlug, availability);
    var curatedModels = merged.curatedModels;
    var liveOnlyModels = merged.liveOnlyModels;

    var matched = findModel(catalog, providerSlug, selectedModel);
    var liveMatch = liveOnlyModels.find(function (model) { return key(model.id) === key(selectedModel); }) || null;
    var resolvedValue = matched ? matched.id : (liveMatch ? liveMatch.id : '');
    var wantsCustom = !!selectedModel && !matched && !liveMatch;
    var legacyProvider = getLegacyModelAliases(catalog)[key(selectedModel)];
    if (legacyProvider && legacyProvider === providerSlug) {
      wantsCustom = false;
      resolvedValue = (provider && provider.default_model) || (curatedModels[0] && curatedModels[0].id) || (liveOnlyModels[0] && liveOnlyModels[0].id) || '';
    }

    if (curatedModels.length) {
      var curatedGroup = document.createElement('optgroup');
      curatedGroup.label = 'Curated catalog';
      appendModelOptions(curatedGroup, curatedModels, resolvedValue);
      selectEl.appendChild(curatedGroup);
    }

    if (liveOnlyModels.length) {
      var liveGroup = document.createElement('optgroup');
      liveGroup.label = 'Live in workspace';
      appendModelOptions(liveGroup, liveOnlyModels, resolvedValue);
      selectEl.appendChild(liveGroup);
    }

    if (provider && provider.allow_custom_model) {
      var customOption = document.createElement('option');
      customOption.value = '__custom__';
      customOption.textContent = 'Custom model id...';
      customOption.selected = wantsCustom || ((!curatedModels.length && !liveOnlyModels.length) && !!selectedModel);
      selectEl.appendChild(customOption);
    }

    if (!curatedModels.length && !liveOnlyModels.length && !(provider && provider.allow_custom_model)) {
      var emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = 'No models available';
      emptyOption.selected = true;
      selectEl.appendChild(emptyOption);
    }

    if (!selectEl.value && selectEl.options.length) {
      selectEl.selectedIndex = 0;
    }

    var useCustom = selectEl.value === '__custom__';
    if (customInputEl) {
      customInputEl.style.display = useCustom ? '' : 'none';
      if (useCustom) {
        customInputEl.value = selectedModel || '';
      } else if (matched) {
        customInputEl.value = matched.id;
      } else if (liveMatch) {
        customInputEl.value = liveMatch.id;
      } else if (!customInputEl.value) {
        customInputEl.value = '';
      }
    }

    if (providerHelperEl) {
      providerHelperEl.textContent = availabilitySummaryText(provider, availability || null);
    }

    if (helperEl) {
      var selected = findModel(catalog, providerSlug, useCustom ? (customInputEl && customInputEl.value) : selectEl.value)
        || liveOnlyModels.find(function (model) {
          return key(model.id) === key(useCustom ? (customInputEl && customInputEl.value) : selectEl.value);
        })
        || null;
      if (selected) {
        var parts = [];
        if (selected._availability === 'live') parts.push('Live in workspace');
        else if (selected._availability === 'catalog') parts.push('Catalog only');
        else parts.push('Unverified');
        if (selected.latest) parts.push('latest');
        if (selected._uncuratedLive) parts.push('returned by provider');
        if (selected.max_output_tokens) parts.push('max out ' + String(selected.max_output_tokens));
        if (selected.notes) parts.push(selected.notes);
        helperEl.textContent = parts.join(' · ');
      } else if (useCustom) {
        helperEl.textContent = 'Custom model id will be saved as-is.';
      } else {
        helperEl.textContent = provider && provider.allow_custom_model
          ? 'Choose a curated model, a live workspace model, or enter a custom id.'
          : 'No curated model list for this provider yet.';
      }
    }

    return {
      selectedModel: useCustom ? (customInputEl ? String(customInputEl.value || '').trim() : '') : String(selectEl.value || '').trim(),
      isCustom: useCustom,
      availability: availability || null,
    };
  }

  function resolveInitialProvider(catalog, selectedProvider, selectedModel) {
    return normalizeProvider(selectedProvider, catalog)
      || inferProviderFromModel(catalog, selectedModel)
      || (listProviders(catalog)[0] && listProviders(catalog)[0].slug)
      || '';
  }

  function availabilityCacheKey(options) {
    return [
      normalizeProvider(options && options.provider, { providers: [], provider_aliases: {} }),
      String(options && options.agentSlug || '').trim(),
      String(options && options.clientId || '').trim()
    ].join('|');
  }

  function loadAvailability(options) {
    var provider = String(options && options.provider || '').trim();
    if (!provider) {
      return Promise.resolve({
        ok: false,
        provider: '',
        status: 'missing_provider',
        credential_mode: 'none',
        validated_at: null,
        live_models: [],
        models: [],
        error: { message: 'missing_provider' }
      });
    }
    var cacheKey = availabilityCacheKey(options);
    if (!availabilityCache[cacheKey]) {
      var params = new URLSearchParams();
      params.set('provider', provider);
      if (options && options.agentSlug) params.set('agent_slug', String(options.agentSlug));
      if (options && options.clientId) params.set('client_id', String(options.clientId));
      availabilityCache[cacheKey] = fetch('/api/llm/availability?' + params.toString(), { cache: 'no-store' })
        .then(function (res) {
          if (!res.ok) throw new Error('llm_availability_http_' + res.status);
          return res.json();
        })
        .catch(function (err) {
          return {
            ok: false,
            provider: provider,
            status: 'unverified',
            credential_mode: 'none',
            validated_at: null,
            live_models: [],
            models: [],
            error: { message: err && err.message ? err.message : 'llm_availability_failed' }
          };
        });
    }
    return availabilityCache[cacheKey];
  }

  function bindControls(config) {
    var providerSelect = config && config.providerSelect;
    var modelSelect = config && config.modelSelect;
    var customModelInput = config && config.customModelInput;
    var providerHelper = config && config.providerHelper;
    var modelHelper = config && config.modelHelper;
    var catalog = config && config.catalog;
    var agentSlug = String(config && config.agentSlug || '').trim();
    var clientId = config && config.clientId;
    if (!providerSelect || !modelSelect || !catalog) return;

    var initialProvider = resolveInitialProvider(catalog, config.selectedProvider, config.selectedModel);
    var bindToken = String(Date.now()) + ':' + Math.random().toString(36).slice(2);
    var currentAvailability = null;

    providerSelect.dataset.llmBindToken = bindToken;
    populateProviderSelect(providerSelect, catalog, initialProvider);
    populateModelSelect({
      selectEl: modelSelect,
      customInputEl: customModelInput,
      helperEl: modelHelper,
      providerHelperEl: providerHelper,
      catalog: catalog,
      providerSlug: initialProvider,
      selectedModel: config.selectedModel,
      availability: null,
    });

    function getCurrentModelSelection() {
      if (!modelSelect) return '';
      if (String(modelSelect.value || '') === '__custom__') {
        return customModelInput ? String(customModelInput.value || '').trim() : '';
      }
      return String(modelSelect.value || '').trim();
    }

    function repaint(selectedModel) {
      populateModelSelect({
        selectEl: modelSelect,
        customInputEl: customModelInput,
        helperEl: modelHelper,
        providerHelperEl: providerHelper,
        catalog: catalog,
        providerSlug: providerSelect.value,
        selectedModel: selectedModel,
        availability: currentAvailability,
      });
    }

    async function refreshAvailability(preferredModel) {
      var provider = String(providerSelect.value || '').trim();
      if (!provider) return;
      if (providerHelper) {
        var providerMeta = getProvider(catalog, provider);
        providerHelper.textContent = availabilitySummaryText(providerMeta, null);
      }
      var requestedToken = providerSelect.dataset.llmBindToken;
      var availability = await loadAvailability({
        provider: provider,
        agentSlug: agentSlug,
        clientId: clientId
      });
      if (providerSelect.dataset.llmBindToken !== requestedToken) return;
      if (key(providerSelect.value) !== key(provider)) return;
      currentAvailability = availability || null;
      repaint(preferredModel || getCurrentModelSelection());
    }

    providerSelect.onchange = function () {
      currentAvailability = null;
      var provider = String(providerSelect.value || '').trim();
      var providerMeta = getProvider(catalog, provider);
      var nextModel = providerMeta && providerMeta.default_model
        ? providerMeta.default_model
        : '';
      repaint(nextModel);
      refreshAvailability(nextModel);
    };

    modelSelect.onchange = function () {
      repaint(modelSelect.value === '__custom__'
        ? (customModelInput ? customModelInput.value : '')
        : modelSelect.value);
    };

    if (customModelInput) {
      customModelInput.oninput = function () {
        repaint(modelSelect.value === '__custom__'
          ? customModelInput.value
          : modelSelect.value);
      };
    }

    refreshAvailability(config.selectedModel);
  }

  function getResolvedSelection(config) {
    var providerSelect = config && config.providerSelect;
    var modelSelect = config && config.modelSelect;
    var customModelInput = config && config.customModelInput;
    var provider = providerSelect ? String(providerSelect.value || '').trim() : '';
    var model = modelSelect ? String(modelSelect.value || '').trim() : '';
    if (model === '__custom__') {
      model = customModelInput ? String(customModelInput.value || '').trim() : '';
    }
    return {
      provider: provider,
      model: model,
    };
  }

  function loadCatalog() {
    if (!catalogPromise) {
      catalogPromise = fetch('/api/llm/catalog', { cache: 'no-store' })
        .then(function (res) {
          if (!res.ok) throw new Error('llm_catalog_http_' + res.status);
          return res.json();
        })
        .catch(function () {
          return { providers: [], provider_aliases: {}, legacy_model_aliases: {} };
        });
    }
    return catalogPromise;
  }

  window.CamaradLlmCatalog = {
    loadCatalog: loadCatalog,
    loadAvailability: loadAvailability,
    listProviders: listProviders,
    getProvider: getProvider,
    normalizeProvider: normalizeProvider,
    inferProviderFromModel: inferProviderFromModel,
    bindControls: bindControls,
    getResolvedSelection: getResolvedSelection,
  };
})();
