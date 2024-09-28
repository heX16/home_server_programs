import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Cpu, HardDrive, Memory } from 'lucide-react';

const formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

const formatUptime = (seconds) => {
  const days = Math.floor(seconds / (3600*24));
  const hours = Math.floor(seconds % (3600*24) / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return `${days}d ${hours}h ${minutes}m`;
};

const SystemMonitor = () => {
  const [systemStatus, setSystemStatus] = useState(null);
  const [diskInfo, setDiskInfo] = useState(null);

  const fetchData = async () => {
    const statusResponse = await fetch('/api/system_status');
    const statusData = await statusResponse.json();
    setSystemStatus(statusData);

    const diskResponse = await fetch('/api/disk');
    const diskData = await diskResponse.json();
    setDiskInfo(diskData);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!systemStatus || !diskInfo) return <div>Loading...</div>;

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-center">System Monitor</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <h3 className="font-bold text-lg">CPU Usage</h3>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemStatus.cpu.usage.toFixed(1)}%</div>
            <Progress value={systemStatus.cpu.usage} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {systemStatus.cpu.cores} Cores
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <h3 className="font-bold text-lg">Memory Usage</h3>
            <Memory className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemStatus.memory.percent.toFixed(1)}%</div>
            <Progress value={systemStatus.memory.percent} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {formatBytes(systemStatus.memory.used)} / {formatBytes(systemStatus.memory.total)}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <h3 className="font-bold text-lg">Uptime</h3>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium">Service Uptime</p>
              <p className="text-2xl font-bold">{formatUptime(systemStatus.uptime.service)}</p>
            </div>
            <div>
              <p className="text-sm font-medium">System Uptime</p>
              <p className="text-2xl font-bold">{formatUptime(systemStatus.uptime.system)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <h3 className="font-bold text-lg">Disk Usage</h3>
          <HardDrive className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {diskInfo.map((disk, index) => (
            <div key={index} className="mb-4">
              <p className="font-medium">{disk.mountpoint}</p>
              <Progress value={disk.usage.percent} className="mt-2" />
              <p className="text-xs text-muted-foreground mt-1">
                {formatBytes(disk.usage.used)} / {formatBytes(disk.usage.total)}
                ({disk.usage.percent.toFixed(1)}%)
              </p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
};

export default SystemMonitor;
