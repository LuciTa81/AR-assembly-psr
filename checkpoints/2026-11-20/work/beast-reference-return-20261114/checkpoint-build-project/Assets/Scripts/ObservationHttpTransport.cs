using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace ARAssembly
{
    // Called on the render thread. Consume the previous reply before the ring's freshness check.
    internal sealed class StageObservationPoll
    {
        private readonly Func<Task<ObservationHttpTransport.Reply>> fetch;
        private Task<ObservationHttpTransport.Reply> pending;
        private double lastStart = double.NegativeInfinity;
        public StageObservationPoll(Func<Task<ObservationHttpTransport.Reply>> fetch) { this.fetch = fetch; }

        public ObservationHttpTransport.Reply Tick(double now, bool screwStage, out double replyStarted)
        {
            replyStarted = lastStart;
            if (pending != null && !pending.IsCompleted) return null;
            var reply = pending?.GetAwaiter().GetResult();
            pending = null;
            // Slight headroom for a nominal 60 Hz display; bounded even with unlocked rendering.
            if (now - lastStart >= (screwStage ? 1.0 / 64 : CandidateProjection.PollIntervalSeconds)) {
                lastStart = now;
                pending = fetch();
            }
            return reply;
        }
    }

    // Loopback metadata only. No Unity APIs or JSON parsing run on the HTTP worker.
    public sealed class ObservationHttpTransport : IDisposable
    {
        public sealed class Reply
        {
            public readonly string Text, Error;
            public readonly double NetworkMs;
            internal Reply(string text, string error, double networkMs)
            { Text = text; Error = error; NetworkMs = networkMs; }
        }

        private readonly HttpClient client;
        private readonly string endpoint;
        private readonly CancellationTokenSource lifetime = new CancellationTokenSource();
        private int disposed, inFlight;

        public ObservationHttpTransport(DisplayCollectionConfig config)
        {
            DisplayCorrespondenceRules.ValidateConfig(config);
            endpoint = config.observation_url;
            client = new HttpClient(new HttpClientHandler {
                AllowAutoRedirect = false, UseProxy = false, UseCookies = false
            }) { Timeout = Timeout.InfiniteTimeSpan };
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", config.token);
            client.DefaultRequestHeaders.CacheControl = new CacheControlHeaderValue { NoCache = true };
        }

        public async Task<Reply> FetchAsync()
        {
            if (Volatile.Read(ref disposed) != 0 || Interlocked.CompareExchange(ref inFlight, 1, 0) != 0)
                return new Reply(null, "CONNECTION ERROR", 0);
            var clock = Stopwatch.StartNew();
            try {
                using (var timeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token)) {
                    timeout.CancelAfter(1000);
                    using (var response = await client.GetAsync(endpoint, HttpCompletionOption.ResponseHeadersRead,
                        timeout.Token).ConfigureAwait(false)) {
                        if (response.StatusCode != System.Net.HttpStatusCode.OK || response.Content.Headers.ContentLength > 65536)
                            return new Reply(null, "CONNECTION ERROR", clock.Elapsed.TotalMilliseconds);
                        using (var stream = await response.Content.ReadAsStreamAsync().ConfigureAwait(false))
                        using (var body = new MemoryStream()) {
                            var buffer = new byte[4096];
                            int count;
                            while ((count = await stream.ReadAsync(buffer, 0, buffer.Length, timeout.Token).ConfigureAwait(false)) != 0) {
                                if (body.Length + count > 65536)
                                    return new Reply(null, "CONNECTION ERROR", clock.Elapsed.TotalMilliseconds);
                                body.Write(buffer, 0, count);
                            }
                            if (timeout.IsCancellationRequested || Volatile.Read(ref disposed) != 0)
                                return new Reply(null, "CONNECTION ERROR", clock.Elapsed.TotalMilliseconds);
                            return new Reply(new UTF8Encoding(false, true).GetString(body.ToArray()), null, clock.Elapsed.TotalMilliseconds);
                        }
                    }
                }
            } catch (Exception exc) when (exc is HttpRequestException || exc is OperationCanceledException
                || exc is IOException || exc is ObjectDisposedException || exc is DecoderFallbackException) {
                return new Reply(null, "CONNECTION ERROR", clock.Elapsed.TotalMilliseconds);
            } finally { Interlocked.Exchange(ref inFlight, 0); }
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref disposed, 1) != 0) return;
            lifetime.Cancel();
            client.Dispose();
            lifetime.Dispose();
        }
    }
}
