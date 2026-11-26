const unityNamespace = {
      unityVersion: '2021.3.45f2c1', 
      assetBundleFSEnabled: true,
      assetBundleBufferCapacity: 128,
      assetBundleBufferTTL: 5,
      // DATA_CDN + dataFileSubPrefix + datafilename
      dataFileSubPrefix:'',
      optimizeWebGLMemoryInBackground: true,
      bootConfig: 'player-connection-ip=192.168.3.241',
	  UnityModule: null,
}
GameGlobal.unityNamespace = GameGlobal.unityNamespace || unityNamespace;
module.exports = unityNamespace;