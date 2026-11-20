using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using ARAssembly;
using NUnit.Framework;

public class ObservationTransportTests
{
    [Test]
    public void StagePollAppliesCompletedReplyAndStartsNextInSameFrameWithoutOverlapping()
    {
        int count=0;
        var pending=new TaskCompletionSource<ObservationHttpTransport.Reply>();
        var pump=new StageObservationPoll(()=>{count++; return pending.Task;});
        Assert.That(pump.Tick(1,true,out _),Is.Null);
        Assert.That(pump.Tick(1.020,true,out _),Is.Null);
        Assert.That(count,Is.EqualTo(1));
        var first=new ObservationHttpTransport.Reply("first",null,2);
        pending.SetResult(first);
        Assert.That(pump.Tick(1.040,true,out var started),Is.SameAs(first));
        Assert.That(started,Is.EqualTo(1)); // Include all time spent waiting to display.
        Assert.That(count,Is.EqualTo(2));
        pump.Tick(1.041,true,out _);
        Assert.That(count,Is.EqualTo(2)); // Never busy-loop on a synchronously completed request.
        pump.Tick(1.057,false,out _);
        Assert.That(count,Is.EqualTo(2)); // Text-only stage retains the slower polling cadence.
        pump.Tick(1.074,false,out _);
        Assert.That(count,Is.EqualTo(3));
    }
    [Test]
    public async Task FetchUsesTheAuthenticatedLoopbackEndpoint()
    {
        using (var fixture = new Fixture(200, "{\"frame_id\":7}"))
        using (var transport = new ObservationHttpTransport(fixture.Config())) {
            var result = await transport.FetchAsync();
            Assert.That(result.Error, Is.Null);
            Assert.That(result.Text, Is.EqualTo("{\"frame_id\":7}"));
            Assert.That(await fixture.Request, Does.StartWith("GET /observation "));
            Assert.That(await fixture.Request, Does.Contain("Authorization: Bearer test-token"));
        }
    }

    [TestCase(401, 2)]
    [TestCase(302, 2)]
    [TestCase(200, 65537)]
    public async Task FetchRejectsHttpFailuresRedirectsAndOversizedBodies(int code, int length)
    {
        using (var fixture = new Fixture(code, new string('x', length)))
        using (var transport = new ObservationHttpTransport(fixture.Config())) {
            var result = await transport.FetchAsync();
            Assert.That(result.Text, Is.Null);
            Assert.That(result.Error, Is.EqualTo("CONNECTION ERROR"));
            Assert.That(fixture.Requests, Is.EqualTo(1));
        }
    }

    [Test]
    public async Task MissingLengthCannotBypassTheStreamingSizeLimit()
    {
        using (var fixture = new Fixture(200, new string('x', 65537), omitLength: true))
        using (var transport = new ObservationHttpTransport(fixture.Config())) {
            Assert.That((await transport.FetchAsync()).Error, Is.EqualTo("CONNECTION ERROR"));
        }
    }

    [Test]
    public async Task CancelRejectsAnInFlightReplyAndFurtherRequests()
    {
        using (var fixture = new Fixture(200, "{}", waitForRelease: true)) {
            var transport = new ObservationHttpTransport(fixture.Config());
            var pending = transport.FetchAsync();
            await fixture.Request;
            transport.Dispose();
            fixture.Release();
            Assert.That((await pending).Error, Is.EqualTo("CONNECTION ERROR"));
            Assert.That((await transport.FetchAsync()).Error, Is.EqualTo("CONNECTION ERROR"));
            Assert.That(fixture.Requests, Is.EqualTo(1));
        }
    }

    [Test]
    public async Task ASecondPollCannotOverlapThePendingRequest()
    {
        using (var fixture = new Fixture(200, "{}", waitForRelease: true))
        using (var transport = new ObservationHttpTransport(fixture.Config())) {
            var first = transport.FetchAsync();
            await fixture.Request;
            Assert.That((await transport.FetchAsync()).Error, Is.EqualTo("CONNECTION ERROR"));
            fixture.Release();
            Assert.That((await first).Text, Is.EqualTo("{}"));
            Assert.That(fixture.Requests, Is.EqualTo(1));
        }
    }

    [TestCase(false)]
    [TestCase(true)]
    public async Task TimeoutCannotLeaveARequestPending(bool delayBody)
    {
        using (var fixture = new Fixture(200, "{}", waitForRelease: true, delayBody: delayBody))
        using (var transport = new ObservationHttpTransport(fixture.Config())) {
            var pending = transport.FetchAsync();
            Assert.That(await Task.WhenAny(pending, Task.Delay(3000)), Is.SameAs(pending));
            Assert.That((await pending).Error, Is.EqualTo("CONNECTION ERROR"));
        }
    }

    [Test]
    public void RenderQueueWaitStillCountsAgainstThePoseBudget()
    {
        var feedback = new DisplayObservationFeedback();
        var observation = DisplayObservationTests.Observation();
        observation.age_ms = 40;
        // Even a fast HTTP response cannot refresh a pose delayed on the main thread.
        feedback.Apply(DisplayObservationTests.Config(), observation, 1, 1.12);
        Assert.That(feedback.Status(1.12), Is.EqualTo("STALE"));
        Assert.That(feedback.TryGetCameraPoint(1.12, out _), Is.False);
    }

    private sealed class Fixture : IDisposable
    {
        private readonly TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
        private readonly TaskCompletionSource<string> request = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource<bool> release = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly Task serving;
        public Task<string> Request => request.Task;
        public int Requests;
        public Fixture(int code, string body, bool waitForRelease = false, bool omitLength = false, bool delayBody = false)
        {
            listener.Start();
            serving = Task.Run(async () => {
                try {
                    using (var client = await listener.AcceptTcpClientAsync())
                    using (var stream = client.GetStream())
                    using (var reader = new StreamReader(stream, Encoding.ASCII, false, 1024, true)) {
                        Interlocked.Increment(ref Requests);
                        var header = new StringBuilder();
                        for (string line = await reader.ReadLineAsync(); !string.IsNullOrEmpty(line); line = await reader.ReadLineAsync())
                            header.AppendLine(line);
                        request.TrySetResult(header.ToString());
                        if (waitForRelease && !delayBody) await release.Task;
                        byte[] data = Encoding.UTF8.GetBytes(body);
                        byte[] head = Encoding.ASCII.GetBytes("HTTP/1.1 " + code + " Test\r\n"
                            + (omitLength ? "" : "Content-Length: " + data.Length + "\r\n")
                            + "Location: http://127.0.0.1:1/forbidden\r\nConnection: close\r\n\r\n");
                        await stream.WriteAsync(head, 0, head.Length);
                        if (waitForRelease && delayBody) await release.Task;
                        await stream.WriteAsync(data, 0, data.Length);
                    }
                } catch (Exception e) when (e is IOException || e is SocketException || e is ObjectDisposedException) {
                    request.TrySetException(e);
                }
            });
        }
        public DisplayCollectionConfig Config()
        {
            var config = DisplayObservationTests.Config();
            config.observation_url = "http://127.0.0.1:" + ((IPEndPoint)listener.LocalEndpoint).Port + "/observation";
            return config;
        }
        public void Release() { release.TrySetResult(true); }
        public void Dispose() { Release(); listener.Stop(); serving.Wait(2000); }
    }
}
