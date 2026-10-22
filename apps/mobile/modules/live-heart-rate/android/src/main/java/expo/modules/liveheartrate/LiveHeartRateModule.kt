package expo.modules.liveheartrate

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import androidx.core.content.ContextCompat
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.util.UUID

/**
 * 标准 BLE 心率服务与心率测量特征。手环开启「心率广播」后会作为外设广播这两个 UUID，
 * 本模块只做中心设备：扫描 → 连接 → 订阅通知 → 把每次心率读数交给 JS。
 */
private val HEART_RATE_SERVICE: ParcelUuid =
  ParcelUuid(UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb"))
private val HEART_RATE_SERVICE_UUID: UUID = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
private val HEART_RATE_MEASUREMENT_UUID: UUID = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
private val CLIENT_CHARACTERISTIC_CONFIG_UUID: UUID =
  UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

/** 一次搜索持续多久。超时后停下并明确告诉用户没找到，避免无限扫描耗电。 */
private const val SCAN_TIMEOUT_MILLIS = 20_000L

class LiveHeartRateModule : Module() {
  private val mainHandler = Handler(Looper.getMainLooper())

  private var gatt: BluetoothGatt? = null
  private var scanning = false
  private var connectedAddress: String? = null
  private var connectedName: String? = null

  private val reactContext: Context?
    get() = appContext.reactContext

  private val adapter: BluetoothAdapter?
    get() {
      val context = reactContext ?: return null
      val manager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
      return manager?.adapter
    }

  override fun definition() = ModuleDefinition {
    Name("LiveHeartRate")

    Events("onDevice", "onSample", "onStatus")

    Function("isAvailable") {
      val context = reactContext
      context != null && context.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)
    }

    AsyncFunction("startScan") {
      requireAdapter()
      requirePermission(scanPermission())
      if (!scanning) {
        val scanner = adapter?.bluetoothLeScanner
          ?: throw IllegalStateException("蓝牙未开启，请先在系统设置里打开蓝牙")
        val filter = ScanFilter.Builder().setServiceUuid(HEART_RATE_SERVICE).build()
        val settings = ScanSettings.Builder()
          .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
          .build()

        scanning = true
        try {
          scanner.startScan(listOf(filter), settings, scanCallback)
        } catch (error: SecurityException) {
          scanning = false
          throw IllegalStateException("缺少蓝牙扫描权限，请在系统设置里允许本应用使用附近的设备")
        }
        emitStatus("scanning")
        mainHandler.postDelayed(scanTimeout, SCAN_TIMEOUT_MILLIS)
      }
    }

    AsyncFunction("stopScan") {
      stopScan("已停止搜索")
    }

    AsyncFunction("connect") { address: String ->
      requireAdapter()
      requirePermission(Manifest.permission.BLUETOOTH_CONNECT)
      stopScan(null)

      val device = resolveDevice(address)
      closeGatt()
      connectedAddress = address
      connectedName = safeDeviceName(device)
      emitStatus("connecting")

      val context = reactContext
        ?: throw IllegalStateException("React context is unavailable")
      val created = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
        ?: throw IllegalStateException("无法连接到 $address")
      gatt = created
    }

    AsyncFunction("disconnect") {
      stopScan(null)
      closeGatt()
      connectedAddress = null
      connectedName = null
      emitStatus("idle")
    }

    OnDestroy {
      mainHandler.removeCallbacks(scanTimeout)
      if (scanning) {
        scanning = false
        runCatching { adapter?.bluetoothLeScanner?.stopScan(scanCallback) }
      }
      closeGatt()
    }
  }

  private fun emit(name: String, body: Bundle) {
    mainHandler.post { sendEvent(name, body) }
  }

  private fun emitStatus(phase: String, message: String? = null) {
    emit(
      "onStatus",
      Bundle().apply {
        putString("phase", phase)
        putString("address", connectedAddress)
        putString("name", connectedName)
        putString("message", message)
      }
    )
  }

  private fun requireAdapter(): BluetoothAdapter {
    val adapter = adapter ?: throw IllegalStateException("此设备不支持蓝牙")
    if (!adapter.isEnabled) throw IllegalStateException("蓝牙未开启，请先在系统设置里打开蓝牙")
    return adapter
  }

  private fun scanPermission(): String =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) Manifest.permission.BLUETOOTH_SCAN
    else Manifest.permission.ACCESS_FINE_LOCATION

  private fun requirePermission(permission: String) {
    val context = reactContext
      ?: throw IllegalStateException("React context is unavailable")
    if (ContextCompat.checkSelfPermission(context, permission) != PackageManager.PERMISSION_GRANTED) {
      throw IllegalStateException("缺少蓝牙权限，请在系统设置里允许本应用使用附近的设备")
    }
  }

  private fun resolveDevice(address: String): BluetoothDevice {
    val adapter = requireAdapter()
    return try {
      adapter.getRemoteDevice(address)
    } catch (error: IllegalArgumentException) {
      throw IllegalStateException("蓝牙地址无效：$address")
    }
  }

  private fun safeDeviceName(device: BluetoothDevice): String? =
    runCatching { device.name }.getOrNull()

  private fun closeGatt() {
    val current = gatt ?: return
    gatt = null
    runCatching { current.disconnect() }
    runCatching { current.close() }
  }

  private fun stopScan(message: String?) {
    mainHandler.removeCallbacks(scanTimeout)
    if (scanning) {
      scanning = false
      runCatching { adapter?.bluetoothLeScanner?.stopScan(scanCallback) }
    }
    emitStatus(if (gatt === null) "idle" else "connecting", message)
  }

  private val scanTimeout = Runnable {
    stopScan("没有找到正在广播心率的手环。请先在手环上开启「心率广播」再重试。")
  }

  private val scanCallback = object : ScanCallback() {
    override fun onScanResult(callbackType: Int, result: ScanResult?) {
      val device = result?.device ?: return
      val address = device.address ?: return
      val advertised = result.scanRecord?.deviceName
      emit(
        "onDevice",
        Bundle().apply {
          putString("address", address)
          putString("name", safeDeviceName(device) ?: advertised)
          putInt("rssi", result.rssi)
        }
      )
    }

    override fun onScanFailed(errorCode: Int) {
      scanning = false
      emitStatus("error", "蓝牙扫描失败（错误码 $errorCode）")
    }
  }

  private val gattCallback = object : BluetoothGattCallback() {
    override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
      if (newState == BluetoothProfile.STATE_CONNECTED) {
        emitStatus("connecting")
        gatt.discoverServices()
        return
      }
      if (newState == BluetoothProfile.STATE_DISCONNECTED) {
        if (this@LiveHeartRateModule.gatt === gatt) closeGatt()
        emitStatus(
          "idle",
          if (status == BluetoothGatt.GATT_SUCCESS) "手环已断开"
          else "与手环的连接中断（状态码 $status）"
        )
      }
    }

    override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
      val characteristic = gatt
        .getService(HEART_RATE_SERVICE_UUID)
        ?.getCharacteristic(HEART_RATE_MEASUREMENT_UUID)
      if (status != BluetoothGatt.GATT_SUCCESS || characteristic == null) {
        closeGatt()
        emitStatus("error", "这个设备没有提供标准心率服务（0x180D），无法读取实时心率")
        return
      }
      if (!gatt.setCharacteristicNotification(characteristic, true)) {
        closeGatt()
        emitStatus("error", "无法订阅心率通知，请重新连接手环")
        return
      }
      val descriptor = characteristic.getDescriptor(CLIENT_CHARACTERISTIC_CONFIG_UUID)
      if (descriptor == null) {
        emitStatus("streaming")
        return
      }
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
      } else {
        @Suppress("DEPRECATION")
        descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        @Suppress("DEPRECATION")
        gatt.writeDescriptor(descriptor)
      }
    }

    override fun onDescriptorWrite(
      gatt: BluetoothGatt,
      descriptor: BluetoothGattDescriptor,
      status: Int,
    ) {
      if (descriptor.uuid != CLIENT_CHARACTERISTIC_CONFIG_UUID) return
      if (status == BluetoothGatt.GATT_SUCCESS) {
        emitStatus("streaming")
      } else {
        emitStatus("error", "订阅心率通知失败（状态码 $status）")
      }
    }

    override fun onCharacteristicChanged(
      gatt: BluetoothGatt,
      characteristic: BluetoothGattCharacteristic,
      value: ByteArray,
    ) {
      if (characteristic.uuid == HEART_RATE_MEASUREMENT_UUID) emitSample(gatt, value)
    }

    @Suppress("OVERRIDE_DEPRECATION", "DEPRECATION")
    override fun onCharacteristicChanged(
      gatt: BluetoothGatt,
      characteristic: BluetoothGattCharacteristic,
    ) {
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) return
      val value = characteristic.value ?: return
      if (characteristic.uuid == HEART_RATE_MEASUREMENT_UUID) emitSample(gatt, value)
    }
  }

  /**
   * 按 Bluetooth SIG 的 Heart Rate Measurement 格式解析一帧数据。
   * flags bit0=1 表示心率是 16 位；bit3 表示带能量消耗（2 字节）；bit4 表示带 RR 间期（每 2 字节一个）。
   */
  private fun emitSample(gatt: BluetoothGatt, value: ByteArray) {
    if (value.size < 2) return

    val flags = value[0].toInt()
    var index = 1
    val beatsPerMinute: Int
    if ((flags and 0x01) != 0) {
      if (value.size < 3) return
      beatsPerMinute = (value[1].toInt() and 0xFF) or ((value[2].toInt() and 0xFF) shl 8)
      index = 3
    } else {
      beatsPerMinute = value[1].toInt() and 0xFF
      index = 2
    }
    if ((flags and 0x08) != 0) index += 2

    val rrIntervals = ArrayList<Int>()
    if ((flags and 0x10) != 0) {
      while (index + 1 < value.size) {
        rrIntervals.add((value[index].toInt() and 0xFF) or ((value[index + 1].toInt() and 0xFF) shl 8))
        index += 2
      }
    }

    // 0 表示接触不良、尚未测到有效搏动，不是一次真实读数。
    if (beatsPerMinute <= 0) return

    emit(
      "onSample",
      Bundle().apply {
        putInt("beatsPerMinute", beatsPerMinute)
        putString("address", connectedAddress ?: gatt.device.address)
        putString("name", connectedName ?: safeDeviceName(gatt.device))
        putDouble("measuredAt", System.currentTimeMillis().toDouble())
        putIntegerArrayList("rrIntervals", rrIntervals)
      }
    )
  }
}
